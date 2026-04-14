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

    def _clear_outline_confirmation(self, session: ComposeSelectionSessionModel) -> None:
        session.outline_confirmed = False
        session.approved_outline_seed_json = None

    def _invalidate_source_selection(self, session: ComposeSelectionSessionModel) -> None:
        session.source_confirmed = False
        self._clear_outline_confirmation(session)

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
            source_confirmed=False,
            outline_confirmed=False,
            preview_version=0,
            approved_outline_seed_json=None,
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
        await db.refresh(session)
        return session

    async def confirm_sources(
        self,
        account_id: str,
        session_id: str,
        db: AsyncSession,
    ) -> ComposeSelectionSessionModel:
        session = await self.get_session(account_id, session_id, db)
        total_selected = len(session.selected_recommendation_ids_json or []) + len(
            session.selected_reference_source_ids_json or []
        )
        if total_selected <= 0:
            raise ValueError("at least one selected source is required before confirming sources")
        session.source_confirmed = True
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    async def confirm_outline(
        self,
        account_id: str,
        session_id: str,
        *,
        preview_version: int,
        approved_outline_seed: dict[str, Any],
        db: AsyncSession,
    ) -> ComposeSelectionSessionModel:
        session = await self.get_session(account_id, session_id, db)
        if not session.source_confirmed:
            raise ValueError("selected sources must be confirmed before confirming the outline")
        if session.preview_version < 1:
            raise ValueError("generate a compose preview before confirming the outline")
        if preview_version != session.preview_version:
            raise ValueError("outline confirmation is stale; regenerate the preview and try again")
        sections = approved_outline_seed.get("sections") if isinstance(approved_outline_seed, dict) else None
        if not isinstance(sections, list) or not sections:
            raise ValueError("approved_outline_seed must include at least one outline section")
        session.outline_confirmed = True
        session.approved_outline_seed_json = approved_outline_seed
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session

    async def validate_submit_ready(
        self,
        account_id: str,
        session_id: str,
        db: AsyncSession,
    ) -> ComposeSelectionSessionModel:
        session = await self.get_session(account_id, session_id, db)
        total_selected = len(session.selected_recommendation_ids_json or []) + len(
            session.selected_reference_source_ids_json or []
        )
        if total_selected <= 0:
            raise ValueError("at least one selected source is required before generation")
        if not session.source_confirmed:
            raise ValueError("selected sources must be confirmed before generation")
        if not session.outline_confirmed or not isinstance(session.approved_outline_seed_json, dict):
            raise ValueError("outline must be confirmed before generation")
        return session

    async def replace_selected_reference_sources(
        self,
        *,
        account_id: str,
        session_id: str,
        reference_source_ids: list[int],
        db: AsyncSession,
    ) -> tuple[ComposeSelectionSessionModel, list[ReferenceSourceModel]]:
        session = await self.get_session(account_id, session_id, db)
        selected_rows = await self._load_reference_sources(account_id, reference_source_ids, db)
        if reference_source_ids and len(selected_rows) != len({int(item) for item in reference_source_ids}):
            raise ValueError("reference_source_ids must all belong to the account")

        session.selected_reference_source_ids_json = [str(row.id) for row in selected_rows]
        self._invalidate_source_selection(session)
        db.add(session)
        await db.flush()
        logger.info(
            "compose_selection_reference_sources_replaced",
            account_id=account_id,
            session_id=session.id,
            reference_source_count=len(selected_rows),
        )
        return session, selected_rows

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
            self._invalidate_source_selection(session)
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
                self._invalidate_source_selection(session)
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
                self._invalidate_source_selection(session)
                db.add(session)
        elif action == "remove_from_creation":
            session = await self.get_session(account_id, selection_session_id, db) if selection_session_id else None
            if session is None:
                raise ValueError("selection_session_id is required for remove_from_creation")
            removed_ids = {row.id for row in recommendations}
            session.selected_recommendation_ids_json = [
                item
                for item in (session.selected_recommendation_ids_json or [])
                if str(item) not in removed_ids
            ]
            self._invalidate_source_selection(session)
            for row in recommendations:
                if row.status == "selected":
                    row.status = "new"
                db.add(row)
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

    async def load_session_bundle(
        self,
        account_id: str,
        session_id: str,
        db: AsyncSession,
    ) -> tuple[
        ComposeSelectionSessionModel,
        list[RecommendedContentItemModel],
        list[ReferenceSourceModel],
    ]:
        session = await self.get_session(account_id, session_id, db)
        selected_recommendations = await self.list_selected_recommendations(account_id, session, db)
        selected_reference_sources = await self.list_selected_reference_sources(account_id, session, db)
        return session, selected_recommendations, selected_reference_sources

    def serialize_session(self, session: ComposeSelectionSessionModel) -> dict[str, Any]:
        return {
            "id": session.id,
            "account_id": session.account_id,
            "selected_recommendation_ids": [str(item) for item in (session.selected_recommendation_ids_json or [])],
            "selected_reference_source_ids": [str(item) for item in (session.selected_reference_source_ids_json or [])],
            "creation_note": session.creation_note,
            "preferred_lane": session.preferred_lane,
            "title_direction": session.title_direction,
            "source_confirmed": session.source_confirmed,
            "outline_confirmed": session.outline_confirmed,
            "preview_version": session.preview_version,
            "approved_outline_seed": session.approved_outline_seed_json,
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

    async def _load_reference_sources(
        self,
        account_id: str,
        reference_source_ids: list[int],
        db: AsyncSession,
    ) -> list[ReferenceSourceModel]:
        valid_ids = [int(item) for item in reference_source_ids if int(item) > 0]
        if not valid_ids:
            return []
        result = await db.execute(
            select(ReferenceSourceModel)
            .where(
                ReferenceSourceModel.account_id == account_id,
                ReferenceSourceModel.id.in_(valid_ids),
            )
            .order_by(desc(ReferenceSourceModel.updated_at), desc(ReferenceSourceModel.id))
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
