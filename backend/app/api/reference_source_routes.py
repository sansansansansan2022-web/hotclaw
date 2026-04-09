"""Account-scoped reference source APIs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.reference_source import (
    ReferenceSourceCreateRequest,
    ReferenceSourceListResponse,
    ReferenceSourceResponse,
    ReferenceSourceUpdateRequest,
    SyncReferenceSourceResponse,
)
from app.services.reference_source_service import reference_source_service

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/accounts/{account_id}/reference-sources",
    tags=["reference-sources"],
)


def _to_response(source) -> ReferenceSourceResponse:
    return ReferenceSourceResponse(
        id=source.id,
        account_id=source.account_id,
        source_type=source.source_type,
        name=source.name,
        source_value=source.source_value,
        notes=source.notes,
        is_enabled=source.is_enabled,
        sync_status=source.sync_status,
        last_synced_at=source.last_synced_at,
        article_count=source.article_count,
        latest_error_message=source.latest_error_message,
        metadata_json=source.metadata_json,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.get("", response_model=ReferenceSourceListResponse)
async def list_reference_sources(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        sources = await reference_source_service.list_sources(account_id, db)
        return ReferenceSourceListResponse(
            account_id=account_id,
            sources=[_to_response(source) for source in sources],
            total=len(sources),
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception as exc:
        logger.error("reference_sources_list_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to load reference sources")


@router.post("", response_model=ReferenceSourceResponse, status_code=201)
async def create_reference_source(
    account_id: str,
    req: ReferenceSourceCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await reference_source_service.create_source(account_id, req.model_dump(), db)
        await db.commit()
        await db.refresh(source)
        return _to_response(source)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("reference_source_create_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to create reference source")


@router.patch("/{source_id}", response_model=ReferenceSourceResponse)
async def update_reference_source(
    account_id: str,
    source_id: int,
    req: ReferenceSourceUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        source = await reference_source_service.update_source(
            account_id, source_id, req.model_dump(exclude_unset=True), db
        )
        await db.commit()
        await db.refresh(source)
        return _to_response(source)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(
            "reference_source_update_error",
            account_id=account_id,
            source_id=source_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="failed to update reference source")


@router.post("/{source_id}/sync", response_model=SyncReferenceSourceResponse)
async def sync_reference_source(
    account_id: str,
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        source, message = await reference_source_service.sync_source(account_id, source_id, db)
        await db.commit()
        await db.refresh(source)
        return SyncReferenceSourceResponse(source=_to_response(source), message=message)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(
            "reference_source_sync_error",
            account_id=account_id,
            source_id=source_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="failed to sync reference source")
