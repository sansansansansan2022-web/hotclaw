"""Compose preview APIs for explicit pre-generation planning."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.compose_preview import ComposePreviewRequest, ComposePreviewResponse
from app.services.compose_preview_service import compose_preview_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts/{account_id}", tags=["compose-preview"])


@router.post("/compose-preview", response_model=ComposePreviewResponse)
async def build_compose_preview(
    account_id: str,
    req: ComposePreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        bundle = await compose_preview_service.build_preview_bundle(
            account_id=account_id,
            selection_session_id=req.selection_session_id,
            creation_note=req.creation_note,
            preferred_lane=req.preferred_lane,
            title_direction=req.title_direction,
            db=db,
        )
        await db.commit()
        return ComposePreviewResponse(**bundle["response"])
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("compose_preview_build_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to build compose preview")
