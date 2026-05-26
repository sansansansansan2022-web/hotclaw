"""Account runtime harness: pre-run ops judgment and effective strategy injection."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func as sa_func, inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import agent_registry
from app.core.logger import get_logger
from app.models.tables import (
    AccountModel,
    ArticleDraftModel,
    ReferenceSourceModel,
    TaskModel,
)
from app.models.wechat_config import WeChatPublishRecordModel
from app.services.automation_plan_service import automation_plan_service

logger = get_logger(__name__)


class AccountHarnessService:
    """Build account run context, call the ops agent, and enforce conservative runtime policy."""

    MIN_REFERENCE_SOURCES_FOR_FULL_AUTO = 2
    PENDING_REVIEW_DEGRADE_THRESHOLD = 3
    PENDING_REVIEW_BLOCK_THRESHOLD = 6
    RECENT_FAILURE_DEGRADE_THRESHOLD = 2
    RECENT_FAILURE_BLOCK_THRESHOLD = 3

    async def evaluate_account_run(
        self,
        account: AccountModel,
        db: AsyncSession,
        *,
        allow_auto: bool = False,
    ) -> dict[str, Any]:
        """Return the normalized ops_context used for a single account run."""

        snapshot = await self._build_input_snapshot(account, db, allow_auto=allow_auto)
        agent_result, fallback_used = await self._run_ops_agent(snapshot)
        ops_context = self._normalize_ops_context(snapshot, agent_result, fallback_used=fallback_used)

        logger.info(
            "account_ops_harness_evaluated",
            account_id=account.id,
            trigger_source=ops_context["trigger"]["source"],
            allow_run=ops_context["run_strategy"]["allow_run"],
            effective_mode=ops_context["run_strategy"]["effective_mode"],
            allow_auto_publish=ops_context["run_strategy"]["allow_auto_publish"],
            fallback_used=ops_context["fallback_used"],
        )
        return ops_context

    def extract_ops_context(
        self,
        input_data: dict[str, Any] | None,
        result_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Read ops_context from task payloads, preferring final result snapshots."""

        if isinstance(result_data, dict) and isinstance(result_data.get("ops_context"), dict):
            return result_data.get("ops_context")
        if isinstance(input_data, dict) and isinstance(input_data.get("ops_context"), dict):
            return input_data.get("ops_context")
        return None

    def extract_run_strategy(
        self,
        input_data: dict[str, Any] | None,
        result_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convenience accessor for downstream services that only need run_strategy."""

        ops_context = self.extract_ops_context(input_data, result_data)
        run_strategy = ops_context.get("run_strategy") if isinstance(ops_context, dict) else None
        return run_strategy if isinstance(run_strategy, dict) else {}

    async def _build_input_snapshot(
        self,
        account: AccountModel,
        db: AsyncSession,
        *,
        allow_auto: bool,
    ) -> dict[str, Any]:
        raw_plan_summary = await automation_plan_service.get_effective_summary(account, db)
        plan_summary = {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in raw_plan_summary.items()
        }

        reference_sources = await self._list_enabled_reference_sources(account.id, db)
        recent_tasks = await self._list_recent_tasks(account.id, db)
        recent_drafts = await self._list_recent_drafts(account.id, db)
        recent_publishes = await self._list_recent_publish_records(account.id, db)
        pending_review_count = await self._count_pending_reviews(account.id, db)

        recent_failed_task_count = sum(1 for task in recent_tasks if task["status"] == "failed")
        recent_failed_publish_count = sum(1 for record in recent_publishes if record["publish_status"] == "failed")
        recent_success_publish_count = sum(1 for record in recent_publishes if record["publish_status"] == "published")
        preferred_content_lane = self._derive_preferred_content_lane(account, recent_drafts)

        return {
            "account": {
                "account_id": account.id,
                "name": account.name,
                "category": account.category,
                "positioning": account.positioning,
                "audience": account.audience,
                "tone_style": account.tone_style,
                "content_strategy": account.content_strategy,
                "is_active": account.is_active,
            },
            "automation_plan": plan_summary,
            "reference_sources": reference_sources,
            "recent_tasks": recent_tasks,
            "recent_drafts": recent_drafts,
            "recent_publishes": recent_publishes,
            "signals": {
                "enabled_reference_source_count": len(reference_sources),
                "pending_review_count": pending_review_count,
                "recent_failed_publish_count": recent_failed_publish_count,
                "recent_success_publish_count": recent_success_publish_count,
                "recent_failed_task_count": recent_failed_task_count,
                "preferred_content_lane": preferred_content_lane,
            },
            "trigger": {
                "source": "scheduler" if allow_auto else "manual",
                "requested_plan_type": plan_summary.get("plan_type") or account.operation_mode,
            },
        }

    async def _run_ops_agent(self, snapshot: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        fallback_used = False
        try:
            agent = agent_registry.get("account_ops_agent")
            result = await agent.execute(snapshot, {"trace_id": ""})
            if result.is_success and isinstance(result.data, dict):
                return result.data, fallback_used

            fallback_used = True
            fallback_result = await agent.fallback(
                RuntimeError(result.error.get("message") if result.error else "ops agent failed"),
                snapshot,
            )
            if fallback_result and fallback_result.is_success and isinstance(fallback_result.data, dict):
                return fallback_result.data, fallback_used
        except Exception as exc:
            logger.warning("account_ops_agent_unavailable", error=str(exc))

        fallback_used = True
        return {
            "account_health": {"status": "attention", "issues": ["Ops agent fallback was required."]},
            "operation_stage": "style_learning",
            "run_strategy": {
                "allow_run": True,
                "effective_mode": str(snapshot.get("automation_plan", {}).get("plan_type") or "manual"),
                "allow_auto_publish": False,
                "preferred_reference_source_ids": [
                    str(item["id"])
                    for item in snapshot.get("reference_sources", [])[:3]
                    if isinstance(item, dict) and item.get("id") is not None
                ],
                "avoid_recent_topics": [],
                "preferred_content_lane": snapshot.get("signals", {}).get("preferred_content_lane"),
            },
            "ops_notes": ["The ops agent was unavailable, so HotClaw fell back to conservative runtime policy."],
        }, fallback_used

    def _normalize_ops_context(
        self,
        snapshot: dict[str, Any],
        agent_data: dict[str, Any],
        *,
        fallback_used: bool,
    ) -> dict[str, Any]:
        account = snapshot["account"]
        plan_summary = snapshot["automation_plan"]
        trigger = snapshot["trigger"]
        signals = snapshot["signals"]

        run_strategy_raw = agent_data.get("run_strategy") if isinstance(agent_data.get("run_strategy"), dict) else {}
        health_raw = agent_data.get("account_health") if isinstance(agent_data.get("account_health"), dict) else {}

        enabled_reference_ids = {
            str(item["id"])
            for item in snapshot["reference_sources"]
            if isinstance(item, dict) and item.get("id") is not None
        }
        preferred_reference_source_ids = [
            str(item).strip()
            for item in run_strategy_raw.get("preferred_reference_source_ids", [])
            if str(item).strip() in enabled_reference_ids
        ]
        if not preferred_reference_source_ids:
            preferred_reference_source_ids = list(enabled_reference_ids)[:3]

        avoid_recent_topics = self._normalize_string_list(run_strategy_raw.get("avoid_recent_topics"))
        if not avoid_recent_topics:
            avoid_recent_topics = self._derive_recent_topics(snapshot["recent_drafts"])

        ops_notes = self._normalize_string_list(agent_data.get("ops_notes"))
        issues = self._normalize_string_list(health_raw.get("issues"))
        operation_stage = str(agent_data.get("operation_stage") or "style_learning")
        requested_mode = str(plan_summary.get("plan_type") or "manual")
        effective_mode = str(run_strategy_raw.get("effective_mode") or requested_mode)
        allow_run = bool(run_strategy_raw.get("allow_run", True))
        allow_auto_publish = bool(run_strategy_raw.get("allow_auto_publish", False))
        preferred_content_lane = (
            str(run_strategy_raw.get("preferred_content_lane")).strip()
            if run_strategy_raw.get("preferred_content_lane")
            else str(signals.get("preferred_content_lane") or "").strip() or None
        )

        mode_rank = {"manual": 0, "semi_auto": 1, "full_auto": 2}
        if effective_mode not in mode_rank:
            effective_mode = requested_mode
        if mode_rank.get(effective_mode, 0) > mode_rank.get(requested_mode, 0):
            effective_mode = requested_mode
            allow_auto_publish = False
            ops_notes.append("Ops agent requested a more permissive mode, so this run was capped to the configured plan.")

        degrade_reasons: list[str] = []
        if requested_mode == "full_auto":
            if signals["enabled_reference_source_count"] < self.MIN_REFERENCE_SOURCES_FOR_FULL_AUTO:
                degrade_reasons.append("reference_sources_insufficient")
            if signals["pending_review_count"] >= self.PENDING_REVIEW_DEGRADE_THRESHOLD:
                degrade_reasons.append("pending_review_backlog")
            if signals["recent_failed_publish_count"] >= self.RECENT_FAILURE_DEGRADE_THRESHOLD:
                degrade_reasons.append("recent_publish_failures")
            if signals["recent_failed_task_count"] >= self.RECENT_FAILURE_DEGRADE_THRESHOLD:
                degrade_reasons.append("recent_task_failures")
            if operation_stage in {"style_learning", "risk_recovery"}:
                degrade_reasons.append(f"operation_stage:{operation_stage}")
            if not allow_auto_publish:
                degrade_reasons.append("ops_agent_disallowed_auto_publish")

        if fallback_used and requested_mode == "full_auto":
            degrade_reasons.append("ops_agent_fallback")

        if degrade_reasons and requested_mode == "full_auto":
            effective_mode = "semi_auto"
            allow_auto_publish = False
            if "This run was downgraded from full-auto to semi-auto for safety." not in ops_notes:
                ops_notes.append("This run was downgraded from full-auto to semi-auto for safety.")

        if effective_mode != "full_auto":
            allow_auto_publish = False

        if trigger["source"] == "scheduler":
            if signals["pending_review_count"] >= self.PENDING_REVIEW_BLOCK_THRESHOLD:
                allow_run = False
                issues.append("Scheduler run blocked because review backlog is too large.")
            if (
                signals["recent_failed_publish_count"] >= self.RECENT_FAILURE_BLOCK_THRESHOLD
                or signals["recent_failed_task_count"] >= self.RECENT_FAILURE_BLOCK_THRESHOLD
            ):
                allow_run = False
                issues.append("Scheduler run blocked because the account is in failure recovery.")

        if fallback_used and requested_mode in {"manual", "semi_auto"}:
            allow_run = True

        account_health_status = str(health_raw.get("status") or "")
        if operation_stage == "risk_recovery" or any("blocked" in issue.lower() for issue in issues):
            account_health_status = "risk_recovery"
        elif issues:
            account_health_status = "attention"
        else:
            account_health_status = "ready"

        context = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "account_health": {
                "status": account_health_status,
                "issues": list(dict.fromkeys(issues)),
            },
            "operation_stage": operation_stage,
            "run_strategy": {
                "allow_run": allow_run,
                "requested_mode": requested_mode,
                "effective_mode": effective_mode,
                "allow_auto_publish": allow_auto_publish,
                "preferred_reference_source_ids": preferred_reference_source_ids,
                "avoid_recent_topics": avoid_recent_topics,
                "preferred_content_lane": preferred_content_lane,
                "degraded_from": requested_mode if effective_mode != requested_mode else None,
                "degrade_reason": ", ".join(degrade_reasons) if degrade_reasons else None,
            },
            "ops_notes": list(dict.fromkeys(ops_notes)),
            "signals": {
                **signals,
                "recent_task_count": len(snapshot["recent_tasks"]),
                "recent_draft_count": len(snapshot["recent_drafts"]),
                "recent_publish_count": len(snapshot["recent_publishes"]),
            },
            "fallback_used": fallback_used,
            "account_summary": {
                "account_id": account["account_id"],
                "account_name": account["name"],
            },
        }

        return context

    async def _list_enabled_reference_sources(
        self,
        account_id: str,
        db: AsyncSession,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(ReferenceSourceModel)
            .where(
                ReferenceSourceModel.account_id == account_id,
                ReferenceSourceModel.is_enabled.is_(True),
            )
            .order_by(desc(ReferenceSourceModel.updated_at), desc(ReferenceSourceModel.id))
            .limit(limit)
        )
        sources = list(result.scalars().all())
        return [
            {
                "id": source.id,
                "name": source.name,
                "source_type": source.source_type,
                "sync_status": source.sync_status,
                "article_count": source.article_count,
            }
            for source in sources
        ]

    async def _list_recent_tasks(
        self,
        account_id: str,
        db: AsyncSession,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(TaskModel)
            .where(TaskModel.account_id == account_id)
            .order_by(desc(TaskModel.created_at), desc(TaskModel.id))
            .limit(limit)
        )
        tasks = list(result.scalars().all())
        summaries: list[dict[str, Any]] = []
        for task in tasks:
            run_strategy = self.extract_run_strategy(task.input_data, task.result_data)
            summaries.append(
                {
                    "task_id": task.id,
                    "status": task.status,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "effective_mode": run_strategy.get("effective_mode"),
                    "error_message": task.error_message,
                }
            )
        return summaries

    async def _list_recent_drafts(
        self,
        account_id: str,
        db: AsyncSession,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(ArticleDraftModel)
            .where(ArticleDraftModel.account_id == account_id)
            .order_by(desc(ArticleDraftModel.updated_at), desc(ArticleDraftModel.id))
            .limit(limit)
        )
        drafts = list(result.scalars().all())
        return [
            {
                "draft_id": draft.id,
                "title": draft.title,
                "selected_topic": draft.selected_topic,
                "draft_status": draft.draft_status,
                "publish_status": draft.publish_status,
                "created_at": draft.created_at.isoformat() if draft.created_at else None,
            }
            for draft in drafts
        ]

    async def _list_recent_publish_records(
        self,
        account_id: str,
        db: AsyncSession,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        available_columns = await self._get_table_columns(db, WeChatPublishRecordModel.__tablename__)
        selected_columns = [
            WeChatPublishRecordModel.id,
            WeChatPublishRecordModel.publish_status,
            WeChatPublishRecordModel.created_at,
            WeChatPublishRecordModel.error_message,
        ]
        include_trigger_type = "trigger_type" in available_columns
        include_source_mode = "source_mode" in available_columns
        if include_trigger_type:
            selected_columns.append(WeChatPublishRecordModel.trigger_type)
        if include_source_mode:
            selected_columns.append(WeChatPublishRecordModel.source_mode)

        result = await db.execute(
            select(*selected_columns)
            .where(WeChatPublishRecordModel.account_id == account_id)
            .order_by(desc(WeChatPublishRecordModel.created_at), desc(WeChatPublishRecordModel.id))
            .limit(limit)
        )
        records = list(result.all())
        summaries: list[dict[str, Any]] = []
        for record in records:
            mapping = record._mapping
            summaries.append(
                {
                    "record_id": mapping.get("id"),
                    "publish_status": mapping.get("publish_status"),
                    "trigger_type": mapping.get("trigger_type"),
                    "source_mode": mapping.get("source_mode"),
                    "created_at": mapping.get("created_at").isoformat() if mapping.get("created_at") else None,
                    "error_message": mapping.get("error_message"),
                }
            )
        return summaries

    async def _get_table_columns(self, db: AsyncSession, table_name: str) -> set[str]:
        def _inspect_columns(sync_session: Any) -> set[str]:
            return {column["name"] for column in sa_inspect(sync_session.bind).get_columns(table_name)}

        return await db.run_sync(_inspect_columns)

    async def _count_pending_reviews(self, account_id: str, db: AsyncSession) -> int:
        result = await db.execute(
            select(sa_func.count())
            .select_from(ArticleDraftModel)
            .where(
                ArticleDraftModel.account_id == account_id,
                ArticleDraftModel.draft_status == "pending_review",
            )
        )
        return int(result.scalar() or 0)

    def _derive_recent_topics(self, recent_drafts: list[dict[str, Any]]) -> list[str]:
        topics: list[str] = []
        for draft in recent_drafts:
            if not isinstance(draft, dict):
                continue
            candidate = str(draft.get("selected_topic") or draft.get("title") or "").strip()
            if candidate and candidate not in topics:
                topics.append(candidate)
            if len(topics) >= 4:
                break
        return topics

    def _derive_preferred_content_lane(
        self,
        account: AccountModel,
        recent_drafts: list[dict[str, Any]],
    ) -> str | None:
        topic_counter: Counter[str] = Counter()
        for draft in recent_drafts:
            topic = str(draft.get("selected_topic") or "").strip()
            if topic:
                topic_counter[topic] += 1
        if topic_counter:
            return topic_counter.most_common(1)[0][0]
        if account.category:
            return account.category
        if account.content_strategy:
            return account.content_strategy.strip()[:80]
        if account.positioning:
            return account.positioning.strip()[:80]
        return None

    def _normalize_string_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned: list[str] = []
        for item in values:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned


account_harness_service = AccountHarnessService()
