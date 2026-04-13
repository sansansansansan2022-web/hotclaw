"""Evidence persistence and workspace shaping."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import EvidenceItemModel

logger = get_logger(__name__)


class EvidenceService:
    """Persist and shape evidence for task workspace consumption."""

    async def persist_items(
        self,
        db: AsyncSession,
        *,
        task_id: str,
        account_id: str | None,
        workspace_id: str,
        skill_name: str,
        evidence_items: list[dict[str, Any]],
    ) -> list[EvidenceItemModel]:
        rows: list[EvidenceItemModel] = []
        for item in evidence_items:
            if not isinstance(item, dict):
                continue
            row = EvidenceItemModel(
                workspace_id=workspace_id,
                task_id=task_id,
                account_id=account_id,
                skill_name=skill_name,
                source_type=str(item.get("source_type") or "").strip(),
                source_id=str(item.get("source_id") or "").strip() or None,
                title=str(item.get("title") or "").strip(),
                url=str(item.get("url") or "").strip() or None,
                summary=str(item.get("summary") or "").strip() or None,
                raw_payload_json=item.get("raw_payload_json"),
                normalized_payload_json=item.get("normalized_payload_json"),
                relevance_score=float(item.get("relevance_score") or 0.0),
                authority_score=float(item.get("authority_score") or 0.0),
                freshness_score=float(item.get("freshness_score") or 0.0),
                practical_score=float(item.get("practical_score") or 0.0),
                selected_reason=str(item.get("selected_reason") or "").strip() or None,
                risk_flags=item.get("risk_flags") if isinstance(item.get("risk_flags"), list) else [],
            )
            db.add(row)
            rows.append(row)
        await db.flush()
        logger.info("evidence_items_persisted", task_id=task_id, skill_name=skill_name, count=len(rows))
        return rows

    def build_workspace_context(self, evidence_rows: list[EvidenceItemModel]) -> dict[str, Any]:
        fetched: list[dict[str, Any]] = []
        selected: list[dict[str, Any]] = []
        summaries: dict[str, str] = {}

        rows_by_skill: dict[str, list[EvidenceItemModel]] = {}
        for row in evidence_rows:
            rows_by_skill.setdefault(str(row.skill_name or "unknown"), []).append(row)

        for skill_name, rows in rows_by_skill.items():
            rows.sort(
                key=lambda item: (
                    float(item.relevance_score or 0.0) + float(item.authority_score or 0.0),
                    float(item.freshness_score or 0.0),
                ),
                reverse=True,
            )
            for row in rows:
                payload = self._row_to_payload(row)
                fetched.append(payload)
            for row in rows[: min(len(rows), 5)]:
                selected.append(self._row_to_payload(row))
            top_titles = ", ".join(row.title for row in rows[:3])
            summaries[skill_name] = f"{skill_name} surfaced {len(rows)} evidence item(s): {top_titles}".strip()

        return {
            "external_evidence": {
                "fetched_evidence": fetched,
                "selected_evidence": selected,
                "evidence_summaries": summaries,
                "citation_guardrails": {
                    "must_ground_titles_in_evidence": True,
                    "must_ground_repo_names_in_evidence": True,
                },
            },
            "fetched_evidence": fetched,
            "selected_evidence": selected,
            "evidence_summaries": summaries,
            "citation_guardrails": {
                "must_ground_titles_in_evidence": True,
                "must_ground_repo_names_in_evidence": True,
            },
        }

    def to_source_candidates(self, evidence_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for index, item in enumerate(evidence_payloads):
            if not isinstance(item, dict):
                continue
            candidates.append(
                {
                    "source_id": str(item.get("source_id") or f"evidence:{index + 1}"),
                    "source_type": item.get("source_type") or "external_evidence",
                    "source_name": item.get("source_type") or "external_evidence",
                    "source_title": item.get("title") or "",
                    "url": item.get("url"),
                    "snippet": item.get("summary") or "",
                    "fit_score": round(
                        (
                            float(item.get("relevance_score") or 0.0)
                            + float(item.get("authority_score") or 0.0)
                            + float(item.get("practical_score") or 0.0)
                        )
                        / 3,
                        4,
                    ),
                    "origin": "external_evidence",
                    "why_selected": item.get("selected_reason") or "",
                }
            )
        return candidates

    async def list_task_evidence(self, db: AsyncSession, task_id: str) -> list[EvidenceItemModel]:
        result = await db.execute(
            select(EvidenceItemModel)
            .where(EvidenceItemModel.task_id == task_id)
            .order_by(desc(EvidenceItemModel.created_at), desc(EvidenceItemModel.id))
        )
        return list(result.scalars().all())

    def serialize_rows(self, rows: list[EvidenceItemModel]) -> list[dict[str, Any]]:
        return [self._row_to_payload(row) for row in rows]

    def _row_to_payload(self, row: EvidenceItemModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "workspace_id": row.workspace_id,
            "task_id": row.task_id,
            "account_id": row.account_id,
            "skill_name": row.skill_name,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "title": row.title,
            "url": row.url,
            "summary": row.summary,
            "raw_payload_json": row.raw_payload_json,
            "normalized_payload_json": row.normalized_payload_json,
            "relevance_score": row.relevance_score,
            "authority_score": row.authority_score,
            "freshness_score": row.freshness_score,
            "practical_score": row.practical_score,
            "selected_reason": row.selected_reason,
            "risk_flags": row.risk_flags or [],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


evidence_service = EvidenceService()
