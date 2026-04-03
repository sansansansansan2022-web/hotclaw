"""Publish decision service.

【发布决策服务】
在真正调用微信发布之前，进行一系列校验，返回四种决策：
- ALLOW_PUBLISH: 允许走真实微信发布链路
- SAVE_AS_DRAFT: 不允许自动发布，保留为待确认草稿
- SKIP: 本次直接跳过，不发、不转待确认
- BLOCK: 直接阻断，记录明确错误

检查项：
A. 系统级开关
B. 账号级检查
C. Draft 状态检查
D. 审核结果门控
E. 发布频率限制
F. 重复内容检查
G. 微信配置检查
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import ArticleDraftModel, AccountModel, AuditResultModel
from app.models.wechat_config import WeChatConfigModel
from app.services.publish_record_service import publish_record_service

logger = get_logger(__name__)


class PublishDecision(str, Enum):
    """Publish decision result types."""
    ALLOW_PUBLISH = "ALLOW_PUBLISH"    # 允许发布
    SAVE_AS_DRAFT = "SAVE_AS_DRAFT"    # 降级为草稿
    SKIP = "SKIP"                       # 跳过本次
    BLOCK = "BLOCK"                     # 阻断


class PublishReasonCode(str, Enum):
    """Reason codes for publish decisions."""
    # System level
    GLOBAL_PUBLISH_DISABLED = "GLOBAL_PUBLISH_DISABLED"
    GLOBAL_EMERGENCY_STOP = "GLOBAL_EMERGENCY_STOP"

    # Account level
    ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    ACCOUNT_PUBLISH_PAUSED = "ACCOUNT_PUBLISH_PAUSED"
    AUTO_PUBLISH_DISABLED = "AUTO_PUBLISH_DISABLED"
    OPERATION_MODE_MISMATCH = "OPERATION_MODE_MISMATCH"

    # Frequency
    DAILY_LIMIT_EXCEEDED = "DAILY_LIMIT_EXCEEDED"
    MIN_INTERVAL_NOT_MET = "MIN_INTERVAL_NOT_MET"

    # Draft state
    DRAFT_NOT_FOUND = "DRAFT_NOT_FOUND"
    DRAFT_ALREADY_PUBLISHED = "DRAFT_ALREADY_PUBLISHED"
    DRAFT_TERMINAL_STATE = "DRAFT_TERMINAL_STATE"
    DRAFT_NO_ACCOUNT = "DRAFT_NO_ACCOUNT"
    ACTIVE_PUBLISH_EXISTS = "ACTIVE_PUBLISH_EXISTS"
    MAX_RETRIES_EXCEEDED = "MAX_RETRIES_EXCEEDED"

    # Audit
    AUDIT_HIGH_RISK = "AUDIT_HIGH_RISK"
    AUDIT_MEDIUM_RISK = "AUDIT_MEDIUM_RISK"

    # Duplicate content
    DUPLICATE_TITLE_EXACT = "DUPLICATE_TITLE_EXACT"
    DUPLICATE_TITLE_SIMILAR = "DUPLICATE_TITLE_SIMILAR"

    # WeChat config
    WECHAT_CONFIG_MISSING = "WECHAT_CONFIG_MISSING"
    WECHAT_CONFIG_DISABLED = "WECHAT_CONFIG_DISABLED"
    WECHAT_CONFIG_INCOMPLETE = "WECHAT_CONFIG_INCOMPLETE"

    # Success
    ALL_CHECKS_PASSED = "ALL_CHECKS_PASSED"


class PublishDecisionError(Exception):
    """Publish decision validation failed."""
    def __init__(self, decision: str, reason_code: str, message: str):
        self.decision = decision
        self.reason_code = reason_code
        self.message = message
        super().__init__(f"[{decision}] {reason_code}: {message}")


class PublishDecisionResult:
    """Structured publish decision result."""
    def __init__(
        self,
        decision: PublishDecision,
        reason_code: PublishReasonCode,
        reason_message: str,
        checks: dict[str, Any] | None = None,
    ):
        self.decision = decision
        self.reason_code = reason_code
        self.reason_message = reason_message
        self.checks = checks or {}

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
    """
    Publish decision service - validates before real publish.

    检查顺序：
    1. 系统级开关（最高优先级）
    2. 账号级检查
    3. Draft 状态检查
    4. 审核结果门控
    5. 发布频率限制
    6. 重复内容检查
    7. 微信配置检查

    返回四种决策：
    - ALLOW_PUBLISH: 所有检查通过
    - SAVE_AS_DRAFT: 降级为待确认草稿（medium risk等）
    - SKIP: 跳过本次（频率限制等）
    - BLOCK: 直接阻断（配置缺失、高风险等）
    """

    # Terminal draft statuses that block publishing
    BLOCKED_DRAFT_STATUSES = {"discarded", "rejected", "published"}

    # Audit risk levels
    RISK_HIGH = "high"
    RISK_MEDIUM = "medium"
    RISK_LOW = "low"

    # Title similarity threshold (0.0 - 1.0)
    TITLE_SIMILARITY_THRESHOLD = 0.70

    async def decide_publish(
        self,
        draft_id: int,
        db: AsyncSession,
        source: str = "manual_confirm",
        is_retry: bool = False,
    ) -> PublishDecisionResult:
        """
        Make publish decision for a draft.

        Args:
            draft_id: Draft ID to validate
            db: Database session
            source: Publish source (full_auto, semi_auto_confirm, manual_confirm, retry)
            is_retry: If True, skip idempotency check (retry case)

        Returns:
            PublishDecisionResult with decision and details
        """
        checks = {}
        draft = None
        account = None
        wechat_config = None

        # ============================================================
        # A. 系统级开关检查 (最高优先级)
        # ============================================================
        global_disabled = await self._check_global_publish_enabled(db)
        checks["global_publish_enabled"] = global_disabled
        if not global_disabled:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.GLOBAL_PUBLISH_DISABLED,
                reason_message="系统发布开关已关闭",
                checks=checks,
            )

        emergency_stop = await self._check_global_emergency_stop(db)
        checks["global_emergency_stop"] = emergency_stop
        if emergency_stop:
            logger.warning("publish_blocked_emergency_stop", draft_id=draft_id)
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.GLOBAL_EMERGENCY_STOP,
                reason_message="系统紧急停止已启用，禁止所有发布",
                checks=checks,
            )

        # ============================================================
        # B. Draft 基础检查
        # ============================================================
        draft = await self._get_draft(draft_id, db)
        if not draft:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.DRAFT_NOT_FOUND,
                reason_message=f"Draft {draft_id} not found",
                checks=checks,
            )
        checks["draft_id"] = draft_id
        checks["draft_status"] = draft.draft_status
        checks["publish_status"] = draft.publish_status

        # Check if already published
        if draft.publish_status == "published":
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.DRAFT_ALREADY_PUBLISHED,
                reason_message=f"Draft {draft_id} already published",
                checks=checks,
            )

        # Check terminal state
        if draft.draft_status in self.BLOCKED_DRAFT_STATUSES:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.DRAFT_TERMINAL_STATE,
                reason_message=f"Draft is in terminal state: {draft.draft_status}",
                checks=checks,
            )

        # ============================================================
        # C. Account 检查
        # ============================================================
        if not draft.account_id:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.DRAFT_NO_ACCOUNT,
                reason_message=f"Draft {draft_id} has no account",
                checks=checks,
            )

        account = await self._get_account(draft.account_id, db)
        if not account:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.ACCOUNT_INACTIVE,
                reason_message=f"Account {draft.account_id} not found",
                checks=checks,
            )

        checks["account_id"] = account.id
        checks["account_name"] = account.name
        checks["operation_mode"] = account.operation_mode
        checks["is_active"] = account.is_active
        checks["publish_paused"] = getattr(account, "publish_paused", False)
        checks["auto_publish_enabled"] = account.auto_publish_enabled

        # Account inactive
        if not account.is_active:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.ACCOUNT_INACTIVE,
                reason_message=f"Account {account.id} is inactive",
                checks=checks,
            )

        # Account publish paused
        if getattr(account, "publish_paused", False):
            logger.info("publish_blocked_account_paused", account_id=account.id, draft_id=draft_id)
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.ACCOUNT_PUBLISH_PAUSED,
                reason_message=f"Account {account.id} publish is paused",
                checks=checks,
            )

        # ============================================================
        # D. Source 与 Operation Mode 校验
        # ============================================================
        if account.operation_mode == "manual":
            # Manual mode: only allow manual_confirm
            if source not in {"manual_confirm"}:
                return PublishDecisionResult(
                    decision=PublishDecision.BLOCK,
                    reason_code=PublishReasonCode.OPERATION_MODE_MISMATCH,
                    reason_message=f"Manual account only accepts manual_confirm, got {source}",
                    checks=checks,
                )

        elif account.operation_mode == "semi_auto":
            # Semi_auto: allow semi_auto_confirm or manual_confirm
            if source not in {"semi_auto_confirm", "manual_confirm"}:
                return PublishDecisionResult(
                    decision=PublishDecision.BLOCK,
                    reason_code=PublishReasonCode.OPERATION_MODE_MISMATCH,
                    reason_message=f"Semi-auto account requires manual confirm, got {source}",
                    checks=checks,
                )

        elif account.operation_mode == "full_auto":
            # Full_auto: source must be full_auto
            if source == "full_auto" and not account.auto_publish_enabled:
                return PublishDecisionResult(
                    decision=PublishDecision.BLOCK,
                    reason_code=PublishReasonCode.AUTO_PUBLISH_DISABLED,
                    reason_message=f"Account {account.id} auto_publish_enabled is false",
                    checks=checks,
                )

        # ============================================================
        # E. 幂等性检查
        # ============================================================
        if not is_retry:
            has_active = await publish_record_service.has_active_publishing(draft_id, db)
            checks["has_active_publishing"] = has_active
            if has_active:
                return PublishDecisionResult(
                    decision=PublishDecision.BLOCK,
                    reason_code=PublishReasonCode.ACTIVE_PUBLISH_EXISTS,
                    reason_message=f"Draft {draft_id} already has active publishing record",
                    checks=checks,
                )

            # Check max retries
            latest = await publish_record_service.get_latest_for_draft(draft_id, db)
            if latest and latest.publish_status == "failed" and latest.retry_count >= 3:
                return PublishDecisionResult(
                    decision=PublishDecision.BLOCK,
                    reason_code=PublishReasonCode.MAX_RETRIES_EXCEEDED,
                    reason_message=f"Draft {draft_id} exceeded maximum retry attempts (3)",
                    checks=checks,
                )

        # ============================================================
        # F. 发布频率限制
        # ============================================================
        frequency_check = await self._check_frequency_limit(account.id, db)
        checks["frequency_check"] = frequency_check

        if not frequency_check["allowed"]:
            if account.operation_mode == "full_auto":
                # Full_auto: skip if over frequency limit
                return PublishDecisionResult(
                    decision=PublishDecision.SKIP,
                    reason_code=PublishReasonCode.DAILY_LIMIT_EXCEEDED
                        if frequency_check.get("daily_exceeded")
                        else PublishReasonCode.MIN_INTERVAL_NOT_MET,
                    reason_message=frequency_check["reason"],
                    checks=checks,
                )
            else:
                # Semi_auto/manual: save as draft
                return PublishDecisionResult(
                    decision=PublishDecision.SAVE_AS_DRAFT,
                    reason_code=PublishReasonCode.DAILY_LIMIT_EXCEEDED
                        if frequency_check.get("daily_exceeded")
                        else PublishReasonCode.MIN_INTERVAL_NOT_MET,
                    reason_message=frequency_check["reason"],
                    checks=checks,
                )

        # ============================================================
        # G. 审核结果门控
        # ============================================================
        audit_check = await self._check_audit_result(draft_id, db)
        checks["audit_check"] = audit_check

        if audit_check.get("risk_level") == self.RISK_HIGH:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.AUDIT_HIGH_RISK,
                reason_message=f"High risk content detected: {audit_check.get('comment', '')}",
                checks=checks,
            )

        if audit_check.get("risk_level") == self.RISK_MEDIUM:
            # Medium risk: save as draft for semi_auto/full_auto, allow for manual
            if source != "manual_confirm":
                return PublishDecisionResult(
                    decision=PublishDecision.SAVE_AS_DRAFT,
                    reason_code=PublishReasonCode.AUDIT_MEDIUM_RISK,
                    reason_message=f"Medium risk content: {audit_check.get('comment', '')}",
                    checks=checks,
                )

        # ============================================================
        # H. 重复内容检查
        # ============================================================
        duplicate_check = await self._check_duplicate_content(account.id, draft.title, db)
        checks["duplicate_check"] = duplicate_check

        if duplicate_check.get("is_exact_match"):
            # Exact title match: skip
            return PublishDecisionResult(
                decision=PublishDecision.SKIP,
                reason_code=PublishReasonCode.DUPLICATE_TITLE_EXACT,
                reason_message=f"Duplicate title found: {duplicate_check.get('matched_title', '')}",
                checks=checks,
            )

        if duplicate_check.get("is_similar"):
            # Similar title: save as draft
            return PublishDecisionResult(
                decision=PublishDecision.SAVE_AS_DRAFT,
                reason_code=PublishReasonCode.DUPLICATE_TITLE_SIMILAR,
                reason_message=f"Similar title found: {duplicate_check.get('matched_title', '')}",
                checks=checks,
            )

        # ============================================================
        # I. 微信配置检查
        # ============================================================
        wechat_config = await self._get_wechat_config(draft.account_id, db)
        checks["wechat_config_exists"] = wechat_config is not None

        if not wechat_config:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.WECHAT_CONFIG_MISSING,
                reason_message=f"WeChat config not found for account {draft.account_id}",
                checks=checks,
            )

        checks["wechat_config_enabled"] = wechat_config.is_enabled

        if not wechat_config.is_enabled:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.WECHAT_CONFIG_DISABLED,
                reason_message=f"WeChat config is disabled for account {draft.account_id}",
                checks=checks,
            )

        checks["wechat_app_id"] = wechat_config.app_id

        if not wechat_config.app_id or not wechat_config.app_secret:
            return PublishDecisionResult(
                decision=PublishDecision.BLOCK,
                reason_code=PublishReasonCode.WECHAT_CONFIG_INCOMPLETE,
                reason_message=f"WeChat config incomplete: app_id or app_secret missing",
                checks=checks,
            )

        # ============================================================
        # J. 所有检查通过
        # ============================================================
        logger.info(
            "publish_decision_passed",
            draft_id=draft_id,
            account_id=account.id,
            source=source,
            decision="ALLOW_PUBLISH"
        )

        return PublishDecisionResult(
            decision=PublishDecision.ALLOW_PUBLISH,
            reason_code=PublishReasonCode.ALL_CHECKS_PASSED,
            reason_message="All checks passed, publish allowed",
            checks=checks,
        )

    async def _check_global_publish_enabled(self, db: AsyncSession) -> bool:
        """Check if global publish is enabled."""
        from app.services.system_config_service import SystemConfigService
        service = SystemConfigService(db)
        enabled = await service.get_typed_value("global_publish_enabled", True)
        return bool(enabled)

    async def _check_global_emergency_stop(self, db: AsyncSession) -> bool:
        """Check if global emergency stop is enabled."""
        from app.services.system_config_service import SystemConfigService
        service = SystemConfigService(db)
        stopped = await service.get_typed_value("global_emergency_stop", False)
        return bool(stopped)

    async def _get_draft(self, draft_id: int, db: AsyncSession) -> ArticleDraftModel | None:
        """Get draft by ID."""
        stmt = select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_account(self, account_id: str, db: AsyncSession) -> AccountModel | None:
        """Get account by ID."""
        stmt = select(AccountModel).where(AccountModel.id == account_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_wechat_config(self, account_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        """Get WeChat config for account."""
        stmt = select(WeChatConfigModel).where(
            WeChatConfigModel.account_id == account_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _check_frequency_limit(
        self,
        account_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Check publish frequency limits.

        Returns:
            dict with:
            - allowed: bool
            - daily_exceeded: bool
            - interval_exceeded: bool
            - today_count: int
            - max_posts_per_day: int | None
            - min_interval_minutes: int | None
            - reason: str
        """
        account = await self._get_account(account_id, db)
        if not account:
            return {"allowed": True}  # Account check will handle this

        max_posts = getattr(account, "max_posts_per_day", None)
        min_interval = getattr(account, "min_interval_minutes", None)

        result = {
            "allowed": True,
            "today_count": 0,
            "max_posts_per_day": max_posts,
            "min_interval_minutes": min_interval,
            "daily_exceeded": False,
            "interval_exceeded": False,
            "reason": "",
        }

        # Check daily limit
        if max_posts is not None and max_posts > 0:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            stmt = (
                select(sa_func.count())
                .select_from(ArticleDraftModel)
                .where(
                    ArticleDraftModel.account_id == account_id,
                    ArticleDraftModel.publish_status == "published",
                    ArticleDraftModel.published_at >= today_start,
                )
            )
            count_result = await db.execute(stmt)
            today_count = count_result.scalar() or 0
            result["today_count"] = today_count

            if today_count >= max_posts:
                result["allowed"] = False
                result["daily_exceeded"] = True
                result["reason"] = f"Daily limit exceeded: {today_count}/{max_posts}"
                return result

        # Check minimum interval
        if min_interval is not None and min_interval > 0:
            latest_published = (
                select(ArticleDraftModel.published_at)
                .where(
                    ArticleDraftModel.account_id == account_id,
                    ArticleDraftModel.publish_status == "published",
                    ArticleDraftModel.published_at.isnot(None),
                )
                .order_by(ArticleDraftModel.published_at.desc())
                .limit(1)
            )
            result_obj = await db.execute(latest_published)
            last_published = result_obj.scalar_one_or_none()

            if last_published:
                now = datetime.now(timezone.utc)
                if last_published.tzinfo is None:
                    last_published = last_published.replace(tzinfo=timezone.utc)
                elapsed_minutes = (now - last_published).total_seconds() / 60

                if elapsed_minutes < min_interval:
                    result["allowed"] = False
                    result["interval_exceeded"] = True
                    result["reason"] = (
                        f"Min interval not met: {elapsed_minutes:.0f}min < {min_interval}min"
                    )
                    return result

        return result

    async def _check_audit_result(
        self,
        draft_id: int,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Check audit result for content risk."""
        stmt = select(AuditResultModel).where(AuditResultModel.draft_id == draft_id)
        result = await db.execute(stmt)
        audit = result.scalar_one_or_none()

        if not audit:
            return {
                "has_audit": False,
                "risk_level": None,
                "passed": None,
                "comment": None,
            }

        return {
            "has_audit": True,
            "risk_level": audit.risk_level,
            "passed": audit.passed,
            "comment": audit.overall_comment,
            "issues": audit.issues,
        }

    async def _check_duplicate_content(
        self,
        account_id: str,
        title: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Check for duplicate content (lightweight, no vector store).

        Checks:
        1. Exact title match with recent published drafts
        2. Similar title (simple string similarity) with recent drafts
        """
        if not title:
            return {"is_exact_match": False, "is_similar": False}

        # Get recent published drafts (last 10)
        recent_drafts = (
            select(ArticleDraftModel)
            .where(
                ArticleDraftModel.account_id == account_id,
                ArticleDraftModel.publish_status == "published",
                ArticleDraftModel.title.isnot(None),
            )
            .order_by(ArticleDraftModel.published_at.desc())
            .limit(10)
        )
        result = await db.execute(recent_drafts)
        recent = list(result.scalars().all())

        title_lower = title.lower().strip()

        for draft in recent:
            if not draft.title:
                continue

            recent_title_lower = draft.title.lower().strip()

            # Exact match
            if recent_title_lower == title_lower:
                return {
                    "is_exact_match": True,
                    "is_similar": False,
                    "matched_title": draft.title,
                    "matched_draft_id": draft.id,
                    "similarity": 1.0,
                }

            # Similarity check (simple)
            similarity = self._calculate_title_similarity(title_lower, recent_title_lower)
            if similarity >= self.TITLE_SIMILARITY_THRESHOLD:
                return {
                    "is_exact_match": False,
                    "is_similar": True,
                    "matched_title": draft.title,
                    "matched_draft_id": draft.id,
                    "similarity": similarity,
                }

        return {
            "is_exact_match": False,
            "is_similar": False,
            "checked_count": len(recent),
        }

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate simple title similarity using common characters."""
        if not title1 or not title2:
            return 0.0

        # Character-based Jaccard similarity
        set1 = set(title1)
        set2 = set(title2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    # Keep backward compatibility
    async def validate_for_publish(
        self,
        draft_id: int,
        db: AsyncSession,
        source: str = "manual_confirm",
        is_retry: bool = False,
    ) -> dict:
        """
        Legacy method for backward compatibility.

        Returns context dict if validation passes.
        Raises PublishDecisionError if validation fails.
        """
        result = await self.decide_publish(draft_id, db, source, is_retry)

        if result.is_block():
            raise PublishDecisionError(
                decision=result.decision.value,
                reason_code=result.reason_code.value,
                message=result.reason_message,
            )

        if result.is_skip():
            raise PublishDecisionError(
                decision=result.decision.value,
                reason_code=result.reason_code.value,
                message=result.reason_message,
            )

        if result.is_save_as_draft():
            raise PublishDecisionError(
                decision=result.decision.value,
                reason_code=result.reason_code.value,
                message=result.reason_message,
            )

        return result.checks

    async def get_wechat_config(
        self,
        account_id: str,
        db: AsyncSession
    ) -> WeChatConfigModel | None:
        """Get WeChat config for an account."""
        return await self._get_wechat_config(account_id, db)


publish_decision_service = PublishDecisionService()
