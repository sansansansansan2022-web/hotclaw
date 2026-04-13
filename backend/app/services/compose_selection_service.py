"""Manage compose selection sessions before formal generation runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.tracer import generate_selection_session_id
from app.models.tables import ComposeSelectionSessionModel, RecommendedContentItemModel, ReferenceSourceModel
from app.services.reference_source_service import reference_source_service

logger = get_logger(__name__)


class ComposeSelectionService:
    """Maintain the current creation basket for an account."""

    async def get_session(
        self,
        account_id: str,
        session_id: str,
        db: AsyncSession,
    ) -> ComposeSelectionSessionModel:
        result = await db.execute(
            select(ComposeSelectionSessionModel).where(
                ComposeSelectionSessionModel.account_id == account_id,
                ComposeSelectionSessionModel.id == session_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"selection session {session_id} was not found for account {account_id}")
        return session

    async def get_or_create_session(
        self,
        account_id: str,
        db: AsyncSession,
        *,
        session_id: str | None = None,
    ) -> ComposeSelectionSessionModel:
        if session_id:
            return await self.get_session(account_id, session_id, db)

        session = ComposeSelectionSessionModel(
            id=generate_selection_session_id(),
            account_id=account_id,
            selected_recommendation_ids_json=[],
            selected_reference_source_ids_json=[],
            status="draft",
        )
        db.add(session)
        await db.flush()
        logger.info("compose_selection_session_created", account_id=account_id, session_id=session.id)
        return session

    async def update_session_preferences(
        self,
        account_id: str,
        session_id: str,
        db: AsyncSession,
        *,
        creation_note: str | None = None,
        preferred_lane: str | None = None,
        title_direction: str | None = None,
        status: str | None = None,
    ) -> ComposeSelectionSessionModel:
        session = await self.get_session(account_id, session_id, db)
        if creation_note is not None:
            session.creation_note = creation_note.strip() or None
        if preferred_lane is not None:
            session.preferred_lane = preferred_lane.strip() or None
        if title_direction is not None:
            session.title_direction = title_direction.strip() or None
        if status is not None:
            session.status = status
        db.add(session)
        await db.flush()
        return session

    async def apply_recommendation_action(
        self,
        *,
        account_id: str,
        recommendation_ids: list[str],
        action: str,
        selection_session_id: str | None,
        db: AsyncSession,
    ) -> tuple[ComposeSelectionSessionModel | None, list[RecommendedContentItemModel], list[ReferenceSourceModel]]:
        recommendations = await self._load_recommendations(account_id, recommendation_ids, db)
        if not recommendations:
            raise ValueError("recommendation_ids must include at least one valid recommendation")

        session: ComposeSelectionSessionModel | None = None
        created_sources: list[ReferenceSourceModel] = []
        if action == "use_for_creation":
            session = await self.get_or_create_session(account_id, db, session_id=selection_session_id)
            selected_ids = list(session.selected_recommendation_ids_json or [])
            for row in recommendations:
                if row.id not in selected_ids:
                    selected_ids.append(row.id)
                row.status = "selected"
                db.add(row)
            session.selected_recommendation_ids_json = selected_ids
            session.status = "draft"
            db.add(session)
        elif action == "save_as_reference":
            session = (
                await self.get_or_create_session(account_id, db, session_id=selection_session_id)
                if selection_session_id
                else None
            )
            for row in recommendations:
                row.status = "saved"
                db.add(row)
                source = await reference_source_service.create_source(
                    account_id,
                    self._recommendation_to_reference_payload(row),
                    db,
                )
                created_sources.append(source)
            if session is not None:
                selected_reference_ids = [str(item) for item in (session.selected_reference_source_ids_json or [])]
                for row in created_sources:
                    if str(row.id) not in selected_reference_ids:
                        selected_reference_ids.append(str(row.id))
                session.selected_reference_source_ids_json = selected_reference_ids
                db.add(session)
        elif action == "dismiss":
            session = (
                await self.get_session(account_id, selection_session_id, db)
                if selection_session_id
                else None
            )
            dismissed_ids = {row.id for row in recommendations}
            for row in recommendations:
                row.status = "dismissed"
                db.add(row)
            if session is not None:
                session.selected_recommendation_ids_json = [
                    item
                    for item in (session.selected_recommendation_ids_json or [])
                    if str(item) not in dismissed_ids
                ]
                db.add(session)
        else:
            raise ValueError(f"unsupported action: {action}")

        await db.flush()

        if session is not None:
            selected_recommendations = await self.list_selected_recommendations(account_id, session, db)
            selected_reference_sources = await self.list_selected_reference_sources(account_id, session, db)
        else:
            selected_recommendations = []
            selected_reference_sources = created_sources

        logger.info(
            "recommendation_selection_updated",
            account_id=account_id,
            action=action,
            recommendation_count=len(recommendations),
            session_id=session.id if session else None,
            reference_source_count=len(selected_reference_sources),
        )
        return session, selected_recommendations, selected_reference_sources

    async def list_selected_recommendations(
        self,
        account_id: str,
        session: ComposeSelectionSessionModel,
        db: AsyncSession,
    ) -> list[RecommendedContentItemModel]:
        selected_ids = [str(item) for item in (session.selected_recommendation_ids_json or []) if str(item).strip()]
        if not selected_ids:
            return []
        result = await db.execute(
            select(RecommendedContentItemModel)
            .where(
                RecommendedContentItemModel.account_id == account_id,
                RecommendedContentItemModel.id.in_(selected_ids),
            )
            .order_by(desc(RecommendedContentItemModel.updated_at), desc(RecommendedContentItemModel.id))
        )
        rows = list(result.scalars().all())
        order = {item: index for index, item in enumerate(selected_ids)}
        rows.sort(key=lambda row: order.get(row.id, len(order)))
        return rows

    async def list_selected_reference_sources(
        self,
        account_id: str,
        session: ComposeSelectionSessionModel,
        db: AsyncSession,
    ) -> list[ReferenceSourceModel]:
        selected_ids = [int(item) for item in (session.selected_reference_source_ids_json or []) if str(item).isdigit()]
        if not selected_ids:
            return []
        result = await db.execute(
            select(ReferenceSourceModel)
            .where(
                ReferenceSourceModel.account_id == account_id,
                ReferenceSourceModel.id.in_(selected_ids),
            )
            .order_by(desc(ReferenceSourceModel.updated_at), desc(ReferenceSourceModel.id))
        )
        rows = list(result.scalars().all())
        order = {item: index for index, item in enumerate(selected_ids)}
        rows.sort(key=lambda row: order.get(row.id, len(order)))
        return rows

    def serialize_session(self, session: ComposeSelectionSessionModel) -> dict[str, Any]:
        return {
            "id": session.id,
            "account_id": session.account_id,
            "selected_recommendation_ids": [str(item) for item in (session.selected_recommendation_ids_json or [])],
            "selected_reference_source_ids": [str(item) for item in (session.selected_reference_source_ids_json or [])],
            "creation_note": session.creation_note,
            "preferred_lane": session.preferred_lane,
            "title_direction": session.title_direction,
            "status": session.status,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def serialize_reference_sources(self, rows: list[ReferenceSourceModel]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for row in rows:
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            payloads.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "source_type": row.source_type,
                    "sync_status": row.sync_status,
                    "notes": row.notes,
                    "preview": metadata.get("preview"),
                }
            )
        return payloads

    async def _load_recommendations(
        self,
        account_id: str,
        recommendation_ids: list[str],
        db: AsyncSession,
    ) -> list[RecommendedContentItemModel]:
        valid_ids = [str(item).strip() for item in recommendation_ids if str(item).strip()]
        if not valid_ids:
            return []
        result = await db.execute(
            select(RecommendedContentItemModel)
            .where(
                RecommendedContentItemModel.account_id == account_id,
                RecommendedContentItemModel.id.in_(valid_ids),
            )
            .order_by(desc(RecommendedContentItemModel.updated_at), desc(RecommendedContentItemModel.id))
        )
        rows = list(result.scalars().all())
        order = {item: index for index, item in enumerate(valid_ids)}
        rows.sort(key=lambda row: order.get(row.id, len(order)))
        return rows

    def _recommendation_to_reference_payload(self, row: RecommendedContentItemModel) -> dict[str, Any]:
        if row.source_url:
            return {
                "source_type": "article_url",
                "name": row.source_name or row.title,
                "source_value": row.source_url,
                "notes": row.reason or row.summary,
                "is_enabled": True,
            }
        content_seed = "\n\n".join(
            [part.strip() for part in [row.title, row.summary or "", row.reason or ""] if part and str(part).strip()]
        )
        return {
            "source_type": "pasted_article",
            "name": row.source_name or row.title,
            "source_value": content_seed or row.title,
            "notes": row.reason or row.summary,
            "is_enabled": True,
        }


compose_selection_service = ComposeSelectionService()
