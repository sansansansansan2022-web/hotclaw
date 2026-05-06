"""Structured publish decision service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import AccountModel, ArticleDraftModel, AuditResultModel, TaskModel
from app.models.wechat_config import WeChatConfigModel
from app.services.account_harness_service import account_harness_service
from app.services.publish_record_service import publish_record_service

logger = get_logger(__name__)


class PublishDecision(str, Enum):
    """Supported decision outcomes before a real publish call."""

    ALLOW_PUBLISH = "ALLOW_PUBLISH"
    SAVE_AS_DRAFT = "SAVE_AS_DRAFT"
    SKIP = "SKIP"
    BLOCK = "BLOCK"


class PublishReasonCode(str, Enum):
    """Reason codes for publish decisions."""

    GLOBAL_PUBLISH_DISABLED = "GLOBAL_PUBLISH_DISABLED"
    GLOBAL_EMERGENCY_STOP = "GLOBAL_EMERGENCY_STOP"
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    ACCOUNT_PUBLISH_PAUSED = "ACCOUNT_PUBLISH_PAUSED"
    AUTO_PUBLISH_DISABLED = "AUTO_PUBLISH_DISABLED"
    OPERATION_MODE_MISMATCH = "OPERATION_MODE_MISMATCH"
    DAILY_LIMIT_EXCEEDED = "DAILY_LIMIT_EXCEEDED"
    MIN_INTERVAL_NOT_MET = "MIN_INTERVAL_NOT_MET"
    DRAFT_NOT_FOUND = "DRAFT_NOT_FOUND"
    DRAFT_ALREADY_PUBLISHED = "DRAFT_ALREADY_PUBLISHED"
    DRAFT_TERMINAL_STATE = "DRAFT_TERMINAL_STATE"
    DRAFT_NO_ACCOUNT = "DRAFT_NO_ACCOUNT"
    ACTIVE_PUBLISH_EXISTS = "ACTIVE_PUBLISH_EXISTS"
    MAX_RETRIES_EXCEEDED = "MAX_RETRIES_EXCEEDED"
    AUDIT_HIGH_RISK = "AUDIT_HIGH_RISK"
    AUDIT_MEDIUM_RISK = "AUDIT_MEDIUM_RISK"
    DUPLICATE_TITLE_EXACT = "DUPLICATE_TITLE_EXACT"
    DUPLICATE_TITLE_SIMILAR = "DUPLICATE_TITLE_SIMILAR"
    WECHAT_CONFIG_MISSING = "WECHAT_CONFIG_MISSING"
    WECHAT_CONFIG_DISABLED = "WECHAT_CONFIG_DISABLED"
    WECHAT_CONFIG_INCOMPLETE = "WECHAT_CONFIG_INCOMPLETE"
    ALL_CHECKS_PASSED = "ALL_CHECKS_PASSED"


class PublishDecisionError(Exception):
    """Raised when a publish request is rejected by policy checks."""

    def __init__(self, decision: str, reason_code: str, message: str):
        self.decision = decision
        self.reason_code = reason_code
        self.message = message
        super().__init__(f"[{decision}] {reason_code}: {message}")


@dataclass(slots=True)
class PublishDecisionResult:
    """Structured result returned by the decision service."""

    decision: PublishDecision
    reason_code: PublishReasonCode
    reason_message: str
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason_code": self.reason_code.value,
            "reason_message": self.reason_message,
            "checks": self.checks,
        }

    def is_block(self) -> bool:
        return self.decision == PublishDecision.BLOCK

    def is_allow(self) -> bool:
        return self.decision == PublishDecision.ALLOW_PUBLISH

    def is_skip(self) -> bool:
        return self.decision == PublishDecision.SKIP

    def is_save_as_draft(self) -> bool:
        return self.decision == PublishDecision.SAVE_AS_DRAFT


class PublishDecisionService:
    """Policy checks that gate real WeChat publishing."""

    BLOCKED_DRAFT_STATUSES = {"discarded", "rejected", "published"}
    ACTIVE_RETRYABLE_STATUSES = {"manual_confirm", "semi_auto_confirm", "manual_retry", "full_auto"}
    TITLE_SIMILARITY_THRESHOLD = 0.70
    RISK_HIGH = "high"
    RISK_MEDIUM = "medium"

    async def decide_publish(
        self,
        draft_id: int,
        db: AsyncSession,
        source: str = "manual_confirm",
        is_retry: bool = False,
    ) -> PublishDecisionResult:
        """Return a structured decision for a publish attempt."""

        checks: dict[str, Any] = {"source": source, "is_retry": is_retry}

        global_enabled = await self._check_global_publish_enabled(db)
        checks["global_publish_enabled"] = global_enabled
        if not global_enabled:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.GLOBAL_PUBLISH_DISABLED,
                "Global publish switch is disabled.",
                checks,
            )

        emergency_stop = await self._check_global_emergency_stop(db)
        checks["global_emergency_stop"] = emergency_stop
        if emergency_stop:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.GLOBAL_EMERGENCY_STOP,
                "Global emergency stop is enabled (紧急停止已启用).",
                checks,
            )

        draft = await self._get_draft(draft_id, db)
        if not draft:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.DRAFT_NOT_FOUND,
                f"Draft {draft_id} does not exist.",
                checks,
            )

        checks["draft_status"] = draft.draft_status
        checks["publish_status"] = draft.publish_status
        checks["draft_account_id"] = draft.account_id

        if draft.publish_status == "published":
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.DRAFT_ALREADY_PUBLISHED,
                f"Draft {draft_id} is already published.",
                checks,
            )

        if draft.draft_status in self.BLOCKED_DRAFT_STATUSES:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.DRAFT_TERMINAL_STATE,
                f"Draft {draft_id} is in terminal state '{draft.draft_status}'.",
                checks,
            )

        if not draft.account_id:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.DRAFT_NO_ACCOUNT,
                f"Draft {draft_id} is not bound to any account.",
                checks,
            )

        account = await self._get_account(draft.account_id, db)
        if not account or not account.is_active:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.ACCOUNT_INACTIVE,
                f"Account {draft.account_id} is inactive or missing.",
                checks,
            )

        from app.services.automation_plan_service import automation_plan_service
        effective_plan = await automation_plan_service.get_effective_summary(account, db)
        effective_mode = effective_plan["plan_type"]
        auto_publish_enabled = effective_plan["auto_publish_enabled"]
        if draft.task_id:
            task_result = await db.execute(select(TaskModel).where(TaskModel.id == draft.task_id))
            task = task_result.scalar_one_or_none()
            if task is not None:
                run_strategy = account_harness_service.extract_run_strategy(task.input_data, task.result_data)
                if run_strategy.get("effective_mode"):
                    effective_mode = str(run_strategy["effective_mode"])
                if "allow_auto_publish" in run_strategy:
                    auto_publish_enabled = bool(run_strategy["allow_auto_publish"])

        checks["account_id"] = account.id
        checks["account_name"] = account.name
        checks["operation_mode"] = effective_mode
        checks["auto_publish_enabled"] = auto_publish_enabled
        checks["publish_paused"] = account.publish_paused

        if account.publish_paused:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.ACCOUNT_PUBLISH_PAUSED,
                f"Account {account.id} publish is paused.",
                checks,
            )

        source_check = self._validate_source(
            effective_mode,
            source,
            bool(auto_publish_enabled),
        )
        if source_check:
            checks.update(source_check["checks"])
            return PublishDecisionResult(
                source_check["decision"],
                source_check["reason_code"],
                source_check["reason_message"],
                checks,
            )

        if not is_retry:
            has_active = await publish_record_service.has_active_publishing(draft_id, db)
            checks["has_active_publishing"] = has_active
            if has_active:
                return PublishDecisionResult(
                    PublishDecision.BLOCK,
                    PublishReasonCode.ACTIVE_PUBLISH_EXISTS,
                    f"Draft {draft_id} already has an active publish record.",
                    checks,
                )

            latest_record = await publish_record_service.get_latest_for_draft(draft_id, db)
            if latest_record and latest_record.publish_status == publish_record_service.STATUS_FAILED:
                checks["latest_retry_count"] = latest_record.retry_count
                if latest_record.retry_count >= 3:
                    return PublishDecisionResult(
                        PublishDecision.BLOCK,
                        PublishReasonCode.MAX_RETRIES_EXCEEDED,
                        f"Draft {draft_id} exceeded maximum retry attempts.",
                        checks,
                    )

        frequency_check = await self._check_frequency_limit(account.id, db, effective_plan)
        checks["frequency_check"] = frequency_check
        if not frequency_check["allowed"]:
            decision = PublishDecision.SKIP if source == "full_auto" else PublishDecision.SAVE_AS_DRAFT
            reason_code = (
                PublishReasonCode.DAILY_LIMIT_EXCEEDED
                if frequency_check["daily_exceeded"]
                else PublishReasonCode.MIN_INTERVAL_NOT_MET
            )
            return PublishDecisionResult(decision, reason_code, frequency_check["reason"], checks)

        audit_check = await self._check_audit_result(draft_id, db)
        checks["audit_check"] = audit_check
        if audit_check["risk_level"] == self.RISK_HIGH:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.AUDIT_HIGH_RISK,
                f"Audit rejected this draft: {audit_check.get('comment') or 'high risk'}",
                checks,
            )
        if audit_check["risk_level"] == self.RISK_MEDIUM and source != "manual_confirm":
            return PublishDecisionResult(
                PublishDecision.SAVE_AS_DRAFT,
                PublishReasonCode.AUDIT_MEDIUM_RISK,
                f"Audit requires manual review: {audit_check.get('comment') or 'medium risk'}",
                checks,
            )

        duplicate_check = await self._check_duplicate_content(account.id, draft.title, db)
        checks["duplicate_check"] = duplicate_check
        if duplicate_check["is_exact_match"]:
            return PublishDecisionResult(
                PublishDecision.SKIP,
                PublishReasonCode.DUPLICATE_TITLE_EXACT,
                f"Duplicate published title found: {duplicate_check['matched_title']}",
                checks,
            )
        if duplicate_check["is_similar"]:
            return PublishDecisionResult(
                PublishDecision.SAVE_AS_DRAFT,
                PublishReasonCode.DUPLICATE_TITLE_SIMILAR,
                f"Similar published title found: {duplicate_check['matched_title']}",
                checks,
            )

        wechat_config = await self._get_wechat_config(account.id, db)
        checks["wechat_config_exists"] = wechat_config is not None
        if not wechat_config:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.WECHAT_CONFIG_MISSING,
                f"WeChat config is missing for account {account.id}.",
                checks,
            )

        checks["wechat_config_enabled"] = wechat_config.is_enabled
        if not wechat_config.is_enabled:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.WECHAT_CONFIG_DISABLED,
                f"WeChat config is disabled for account {account.id}.",
                checks,
            )

        if not wechat_config.app_id or not wechat_config.app_secret:
            return PublishDecisionResult(
                PublishDecision.BLOCK,
                PublishReasonCode.WECHAT_CONFIG_INCOMPLETE,
                f"WeChat config is incomplete for account {account.id}.",
                checks,
            )

        logger.info("publish_decision_allow", draft_id=draft_id, account_id=account.id, source=source)
        return PublishDecisionResult(
            PublishDecision.ALLOW_PUBLISH,
            PublishReasonCode.ALL_CHECKS_PASSED,
            "All checks passed.",
            checks,
        )

    def _validate_source(
        self,
        operation_mode: str,
        source: str,
        auto_publish_enabled: bool,
    ) -> dict[str, Any] | None:
        if operation_mode == "manual" and source not in {"manual_confirm", "manual_retry"}:
            return {
                "decision": PublishDecision.BLOCK,
                "reason_code": PublishReasonCode.OPERATION_MODE_MISMATCH,
                "reason_message": f"Manual account does not allow source '{source}'.",
                "checks": {},
            }

        if operation_mode == "semi_auto" and source not in {"manual_confirm", "semi_auto_confirm", "manual_retry"}:
            return {
                "decision": PublishDecision.BLOCK,
                "reason_code": PublishReasonCode.OPERATION_MODE_MISMATCH,
                "reason_message": f"Semi-auto account does not allow source '{source}'.",
                "checks": {},
            }

        if source == "full_auto" and not auto_publish_enabled:
            return {
                "decision": PublishDecision.BLOCK,
                "reason_code": PublishReasonCode.AUTO_PUBLISH_DISABLED,
                "reason_message": "Auto publish is disabled for this account.",
                "checks": {"auto_publish_enabled": auto_publish_enabled},
            }

        return None

    async def _check_global_publish_enabled(self, db: AsyncSession) -> bool:
        from app.services.system_config_service import SystemConfigService

        service = SystemConfigService(db)
        return bool(await service.get_typed_value("global_publish_enabled", True))

    async def _check_global_emergency_stop(self, db: AsyncSession) -> bool:
        from app.services.system_config_service import SystemConfigService

        service = SystemConfigService(db)
        return bool(await service.get_typed_value("global_emergency_stop", False))

    async def _get_draft(self, draft_id: int, db: AsyncSession) -> ArticleDraftModel | None:
        result = await db.execute(select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id))
        return result.scalar_one_or_none()

    async def _get_account(self, account_id: str, db: AsyncSession) -> AccountModel | None:
        result = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
        return result.scalar_one_or_none()

    async def _get_wechat_config(self, account_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        result = await db.execute(select(WeChatConfigModel).where(WeChatConfigModel.account_id == account_id))
        return result.scalar_one_or_none()

    async def _check_frequency_limit(
        self,
        account_id: str,
        db: AsyncSession,
        effective_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        account = await self._get_account(account_id, db)
        if not account:
            return {"allowed": True, "daily_exceeded": False, "interval_exceeded": False, "reason": ""}

        max_posts = (
            effective_plan.get("max_posts_per_day")
            if effective_plan is not None
            else account.max_posts_per_day
        )
        min_interval = (
            effective_plan.get("min_interval_minutes")
            if effective_plan is not None
            else account.min_interval_minutes
        )
        result = {
            "allowed": True,
            "daily_exceeded": False,
            "interval_exceeded": False,
            "today_count": 0,
            "max_posts_per_day": max_posts,
            "min_interval_minutes": min_interval,
            "reason": "",
        }

        if max_posts:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            count_stmt = (
                select(sa_func.count())
                .select_from(ArticleDraftModel)
                .where(
                    ArticleDraftModel.account_id == account_id,
                    ArticleDraftModel.publish_status == "published",
                    ArticleDraftModel.published_at >= today_start,
                )
            )
            count_result = await db.execute(count_stmt)
            today_count = count_result.scalar() or 0
            result["today_count"] = today_count
            if today_count >= max_posts:
                result["allowed"] = False
                result["daily_exceeded"] = True
                result["reason"] = f"Daily limit exceeded: {today_count}/{max_posts}"
                return result

        if min_interval:
            published_stmt = (
                select(ArticleDraftModel.published_at)
                .where(
                    ArticleDraftModel.account_id == account_id,
                    ArticleDraftModel.publish_status == "published",
                    ArticleDraftModel.published_at.isnot(None),
                )
                .order_by(ArticleDraftModel.published_at.desc())
                .limit(1)
            )
            published_result = await db.execute(published_stmt)
            last_published = published_result.scalar_one_or_none()
            if last_published:
                if last_published.tzinfo is None:
                    last_published = last_published.replace(tzinfo=timezone.utc)
                elapsed_minutes = (datetime.now(timezone.utc) - last_published).total_seconds() / 60
                if elapsed_minutes < min_interval:
                    result["allowed"] = False
                    result["interval_exceeded"] = True
                    result["reason"] = f"Minimum interval not met: {elapsed_minutes:.0f} < {min_interval} minutes"
                    return result

        return result

    async def _check_audit_result(self, draft_id: int, db: AsyncSession) -> dict[str, Any]:
        result = await db.execute(select(AuditResultModel).where(AuditResultModel.draft_id == draft_id))
        audit = result.scalar_one_or_none()
        if not audit:
            return {"has_audit": False, "risk_level": None, "passed": None, "comment": None, "issues": None}
        return {
            "has_audit": True,
            "risk_level": audit.risk_level,
            "passed": audit.passed,
            "comment": audit.overall_comment,
            "issues": audit.issues,
        }

    async def _check_duplicate_content(self, account_id: str, title: str, db: AsyncSession) -> dict[str, Any]:
        if not title:
            return {"is_exact_match": False, "is_similar": False}

        stmt = (
            select(ArticleDraftModel)
            .where(
                ArticleDraftModel.account_id == account_id,
                ArticleDraftModel.publish_status == "published",
                ArticleDraftModel.title.isnot(None),
            )
            .order_by(ArticleDraftModel.published_at.desc())
            .limit(10)
        )
        result = await db.execute(stmt)
        recent = list(result.scalars().all())
        normalized_title = title.strip().lower()
        for draft in recent:
            if not draft.title:
                continue
            recent_title = draft.title.strip().lower()
            if recent_title == normalized_title:
                return {
                    "is_exact_match": True,
                    "is_similar": False,
                    "matched_title": draft.title,
                    "matched_draft_id": draft.id,
                    "similarity": 1.0,
                }
            similarity = self._calculate_title_similarity(normalized_title, recent_title)
            if similarity >= self.TITLE_SIMILARITY_THRESHOLD:
                return {
                    "is_exact_match": False,
                    "is_similar": True,
                    "matched_title": draft.title,
                    "matched_draft_id": draft.id,
                    "similarity": similarity,
                }
        return {"is_exact_match": False, "is_similar": False, "checked_count": len(recent)}

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        if not title1 or not title2:
            return 0.0
        set1 = set(title1)
        set2 = set(title2)
        union = len(set1 | set2)
        if union == 0:
            return 0.0
        return len(set1 & set2) / union

    async def validate_for_publish(
        self,
        draft_id: int,
        db: AsyncSession,
        source: str = "manual_confirm",
        is_retry: bool = False,
    ) -> dict[str, Any]:
        result = await self.decide_publish(draft_id, db, source=source, is_retry=is_retry)
        if not result.is_allow():
            raise PublishDecisionError(
                decision=result.decision.value,
                reason_code=result.reason_code.value,
                message=result.reason_message,
            )
        return result.checks

    async def get_wechat_config(self, account_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        return await self._get_wechat_config(account_id, db)


publish_decision_service = PublishDecisionService()
