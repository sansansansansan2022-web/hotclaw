"""Context builder: first DAG node — merge profiles, ops harness, memories."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.core.logger import get_logger
from app.models.tables import AccountModel
from app.services.account_harness_service import account_harness_service
from app.services.account_onboarding_service import account_onboarding_service
from app.services.account_service import account_service
from app.services.memory_service import memory_service, serialize_memory

logger = get_logger(__name__)


def _deep_merge_dicts(base: dict[str, Any], *overlays: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = deepcopy(base) if base else {}
    for overlay in overlays:
        if not overlay:
            continue
        for key, value in overlay.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _deep_merge_dicts(merged[key], value)
            else:
                merged[key] = deepcopy(value) if isinstance(value, dict) else value
    return merged


class ContextBuilderAgent(BaseAgent):
    """
    Merge base / evolved / style profiles, evaluate ops_context, fetch memories.

    Contract output (run_context payload):
    - effective_profile, account_context, ops_context, retrieved_memories, positioning
    """

    agent_id = "context_builder_agent"
    name = "上下文装配器"
    description = "合并三层 profile + 运营策略 + retrieved_memories，产出 RunContext 注入后续所有节点"

    input_schema = {
        "type": "object",
        "properties": {
            "positioning": {"type": "string"},
            "account_id": {"type": "string"},
        },
    }
    output_schema = {"type": "object"}
    supported_skills = []

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        db = context.get("db")
        if not isinstance(db, AsyncSession):
            return self._fallback_run(input_data, reason="missing_db_session")

        account_id = input_data.get("account_id") or input_data.get("accountId")
        positioning = (input_data.get("positioning") or "").strip()

        try:
            account: AccountModel | None = None
            if account_id:
                result = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
                account = result.scalar_one_or_none()

            if account and not positioning:
                positioning = (account.positioning or "").strip()

            base: dict[str, Any] = {}
            evolved: dict[str, Any] = {}
            style: dict[str, Any] = {}

            if account:
                if not account.base_profile_json:
                    await account_onboarding_service.parse_positioning(account, db)
                base = dict(account.base_profile_json or {})
                evolved = dict(account.evolved_profile_json or {})
                style = dict(account.style_profile_json or {})
            else:
                base = await account_onboarding_service.build_structured_profile_from_positioning(positioning)

            effective_profile = _deep_merge_dicts(base, evolved, style)

            account_context = await account_service.get_account_context(
                str(account_id) if account_id else None,
                db,
            )
            if isinstance(account_context, dict):
                account_context = {**account_context, "profile": effective_profile}
            elif account_context is None and (account_id or positioning or account):
                account_context = {
                    "account_id": account_id,
                    "positioning": positioning or (account.positioning if account else ""),
                    "profile": effective_profile,
                }

            ops_context: dict[str, Any] = {}
            if account:
                ops_context = await account_harness_service.evaluate_account_run(account, db, allow_auto=False)

            retrieved_memories: list[dict[str, Any]] = []
            if account_id:
                memory_rows = await memory_service.retrieve_relevant(
                    str(account_id),
                    positioning or (account.positioning if account else ""),
                    db,
                    limit=5,
                )
                retrieved_memories = [serialize_memory(m) for m in memory_rows]

            out = {
                "effective_profile": effective_profile,
                "account_context": account_context,
                "ops_context": ops_context,
                "retrieved_memories": retrieved_memories,
                "positioning": positioning or (account.positioning if account else ""),
            }
            return self._success(out)
        except Exception as exc:
            logger.warning("context_builder_failed", error=str(exc), account_id=account_id)
            return self._fallback_run(input_data, reason=str(exc))

    def _fallback_run(self, input_data: dict, *, reason: str) -> AgentResult:
        positioning = (input_data.get("positioning") or "").strip()
        logger.info("context_builder_fallback", reason=reason)
        return self._success(
            {
                "effective_profile": {},
                "account_context": {"positioning": positioning} if positioning else None,
                "ops_context": {},
                "retrieved_memories": [],
                "positioning": positioning,
            }
        )

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        return self._fallback_run(input_data, reason=str(error))
