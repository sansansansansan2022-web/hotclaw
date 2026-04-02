"""Draft API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.exceptions import (
    DraftNotFoundError,
    DraftInvalidStatusError,
    DraftAlreadyPublishedError,
    DraftPublishError,
    DraftCreateError,
)
from app.core.logger import get_logger
from app.schemas.draft import (
    DraftSummary,
    DraftDetail,
    DraftListResponse,
    DraftConfirmData,
    DraftDiscardData,
    DraftRejectData,
    DraftRerunData,
    AuditResultInfo,
)
from app.services.draft_service import draft_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])


@router.get("", response_model=DraftListResponse)
async def list_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_id: str | None = Query(None),
    draft_status: str | None = Query(None),
    publish_status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List drafts with pagination and filters."""
    try:
        drafts, total = await draft_service.list_drafts(
            db,
            page=page,
            page_size=page_size,
            account_id=account_id,
            draft_status=draft_status,
            publish_status=publish_status,
        )
        return DraftListResponse(
            drafts=[
                DraftSummary(
                    id=d.id,
                    task_id=d.task_id,
                    account_id=d.account_id,
                    title=d.title,
                    selected_topic=d.selected_topic,
                    draft_status=d.draft_status,
                    publish_status=d.publish_status,
                    publish_review_required=d.publish_review_required,
                    source_type=d.source_type,
                    word_count=d.word_count,
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                )
                for d in drafts
            ],
            pagination={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        )
    except Exception as e:
        logger.error("draft_list_error", error=str(e))
        raise


@router.get("/{draft_id}", response_model=DraftDetail)
async def get_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get draft detail with audit result."""
    try:
        detail = await draft_service.get_draft_detail(draft_id, db)
        from datetime import datetime
        for dt_field in ["confirmed_at", "published_at", "created_at", "updated_at"]:
            if detail.get(dt_field) and isinstance(detail[dt_field], str):
                detail[dt_field] = datetime.fromisoformat(detail[dt_field])
        return DraftDetail(**detail)
    except DraftNotFoundError as e:
        logger.warning("draft_get_not_found", draft_id=draft_id)
        raise
    except Exception as e:
        logger.error("draft_get_error", draft_id=draft_id, error=str(e))
        raise


@router.post("/{draft_id}/confirm-publish", response_model=DraftConfirmData)
async def confirm_publish_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm draft publish.

    State transition: pending_review -> approved -> published
    """
    try:
        draft = await draft_service.confirm_publish(draft_id, db)
        await db.commit()
        return DraftConfirmData(
            draft_id=draft.id,
            draft_status=draft.draft_status,
            publish_status=draft.publish_status,
            confirmed_at=draft.confirmed_at,
        )
    except DraftNotFoundError as e:
        logger.warning("draft_confirm_not_found", draft_id=draft_id)
        raise
    except DraftInvalidStatusError as e:
        logger.warning("draft_confirm_invalid_status", draft_id=draft_id, error=e.message)
        raise
    except DraftPublishError as e:
        logger.error("draft_confirm_publish_error", draft_id=draft_id, error=e.message)
        raise
    except Exception as e:
        logger.error("draft_confirm_error", draft_id=draft_id, error=str(e))
        raise


@router.post("/{draft_id}/discard", response_model=DraftDiscardData)
async def discard_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Discard a draft.

    State transition: pending_review -> discarded
    """
    try:
        draft = await draft_service.discard_draft(draft_id, db)
        await db.commit()
        return DraftDiscardData(
            draft_id=draft.id,
            draft_status=draft.draft_status,
        )
    except DraftNotFoundError as e:
        logger.warning("draft_discard_not_found", draft_id=draft_id)
        raise
    except DraftInvalidStatusError as e:
        logger.warning("draft_discard_invalid_status", draft_id=draft_id, error=e.message)
        raise
    except Exception as e:
        logger.error("draft_discard_error", draft_id=draft_id, error=str(e))
        raise


@router.post("/{draft_id}/reject", response_model=DraftRejectData)
async def reject_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a draft.

    State transition: pending_review -> rejected
    """
    try:
        draft = await draft_service.reject_draft(draft_id, db)
        await db.commit()
        return DraftRejectData(
            draft_id=draft.id,
            draft_status=draft.draft_status,
        )
    except DraftNotFoundError as e:
        logger.warning("draft_reject_not_found", draft_id=draft_id)
        raise
    except DraftInvalidStatusError as e:
        logger.warning("draft_reject_invalid_status", draft_id=draft_id, error=e.message)
        raise
    except Exception as e:
        logger.error("draft_reject_error", draft_id=draft_id, error=str(e))
        raise


@router.post("/{draft_id}/rerun", response_model=DraftRerunData)
async def rerun_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Rerun a task based on the draft's account.

    Creates a new task with the same positioning as the original task.
    """
    try:
        original_draft, new_task = await draft_service.rerun_from_draft(draft_id, db)
        await db.commit()
        return DraftRerunData(
            draft_id=original_draft.id,
            original_task_id=original_draft.task_id,
            new_task_id=new_task.id,
            status=new_task.status,
        )
    except DraftNotFoundError as e:
        logger.warning("draft_rerun_not_found", draft_id=draft_id)
        raise
    except DraftCreateError as e:
        logger.warning("draft_rerun_create_error", draft_id=draft_id, error=e.message)
        raise
    except Exception as e:
        logger.error("draft_rerun_error", draft_id=draft_id, error=str(e))
        raise


@router.get("/pending-count")
async def get_pending_review_count(
    account_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get count of pending review drafts for an account.

    Can be filtered by account_id.
    """
    try:
        count = await draft_service.get_pending_review_count(db, account_id)
        return {"count": count, "account_id": account_id}
    except Exception as e:
        logger.error("draft_pending_count_error", error=str(e))
        raise
