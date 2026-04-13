"""Runtime orchestration for skill invocation, cache, and evidence."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillExecutionError
from app.core.logger import get_logger
from app.models.tables import SkillInvocationLogModel
from app.skills.registry import skill_registry
from app.skills.services.evidence_service import evidence_service
from app.skills.services.skill_cache_service import skill_cache_service

logger = get_logger(__name__)


class SkillRuntimeService:
    """Central runtime entry for externally backed skills."""

    async def invoke(
        self,
        *,
        skill_name: str,
        input_data: dict[str, Any],
        db: AsyncSession,
        task_id: str,
        workspace_id: str,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        skill = skill_registry.get(skill_name)
        request_fingerprint = skill_cache_service.build_request_fingerprint(skill_name, input_data)
        invocation = SkillInvocationLogModel(
            task_id=task_id,
            workspace_id=workspace_id,
            account_id=account_id,
            skill_name=skill_name,
            request_fingerprint=request_fingerprint,
            input_json=input_data,
            status="started",
        )
        db.add(invocation)
        await db.flush()

        started = perf_counter()
        try:
            cached = await skill_cache_service.get(
                db,
                skill_name=skill_name,
                request_fingerprint=request_fingerprint,
            )
            from_cache = cached is not None
            response = cached if cached is not None else await skill.execute(input_data)
            if not isinstance(response, dict) or response.get("status") != "success":
                error = response.get("error") if isinstance(response, dict) else {}
                raise SkillExecutionError(
                    skill_name,
                    str((error or {}).get("message") or "unknown skill failure"),
                )

            if not from_cache:
                await skill_cache_service.set(
                    db,
                    skill_name=skill_name,
                    request_fingerprint=request_fingerprint,
                    response_json=response,
                )

            data = response.get("data") or {}
            evidence_rows = await evidence_service.persist_items(
                db,
                task_id=task_id,
                account_id=account_id,
                workspace_id=workspace_id,
                skill_name=skill_name,
                evidence_items=data.get("evidence_items") or [],
            )
            workspace_payload = evidence_service.build_workspace_context(evidence_rows)

            invocation.status = "success"
            invocation.output_json = {
                **data,
                "workspace_evidence": workspace_payload,
                "from_cache": from_cache,
            }
            invocation.latency_ms = int((perf_counter() - started) * 1000)
            db.add(invocation)
            await db.flush()

            logger.info(
                "skill_invocation_succeeded",
                task_id=task_id,
                skill_name=skill_name,
                from_cache=from_cache,
                evidence_count=len(evidence_rows),
                latency_ms=invocation.latency_ms,
            )
            return {
                "skill_name": skill_name,
                "reason": "",
                "from_cache": from_cache,
                "data": data,
                "workspace_payload": workspace_payload,
            }
        except Exception as exc:
            invocation.status = "failed"
            invocation.error_message = str(exc)
            invocation.latency_ms = int((perf_counter() - started) * 1000)
            db.add(invocation)
            await db.flush()
            logger.error("skill_invocation_failed", task_id=task_id, skill_name=skill_name, error=str(exc))
            raise

    async def list_task_invocations(self, db: AsyncSession, task_id: str) -> list[SkillInvocationLogModel]:
        result = await db.execute(
            select(SkillInvocationLogModel)
            .where(SkillInvocationLogModel.task_id == task_id)
            .order_by(desc(SkillInvocationLogModel.created_at), desc(SkillInvocationLogModel.id))
        )
        return list(result.scalars().all())

    def serialize_invocations(self, rows: list[SkillInvocationLogModel]) -> list[dict[str, Any]]:
        return [
            {
                "id": row.id,
                "task_id": row.task_id,
                "workspace_id": row.workspace_id,
                "account_id": row.account_id,
                "skill_name": row.skill_name,
                "request_fingerprint": row.request_fingerprint,
                "input_json": row.input_json,
                "output_json": row.output_json,
                "status": row.status,
                "latency_ms": row.latency_ms,
                "error_message": row.error_message,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]


skill_runtime_service = SkillRuntimeService()
