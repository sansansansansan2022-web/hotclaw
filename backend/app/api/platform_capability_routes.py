"""Platform capability plugin management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.platform_capability import (
    EffectivePlatformCapabilityResponse,
    PlatformCapabilityCreateRequest,
    PlatformCapabilityListResponse,
    PlatformCapabilityResponse,
    PlatformCapabilityUpdateRequest,
)
from app.services.platform_capability_service import platform_capability_service

router = APIRouter(prefix="/api/v1/platform-capabilities", tags=["platform-capabilities"])


@router.get("", response_model=PlatformCapabilityListResponse)
async def list_platform_capabilities(
    content_platform: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> PlatformCapabilityListResponse:
    rows = await platform_capability_service.list_capabilities(
        db,
        content_platform=content_platform,
        include_deleted=include_deleted,
    )
    return PlatformCapabilityListResponse(
        capabilities=[PlatformCapabilityResponse(**row) for row in rows],
        total=len(rows),
        enabled_count=sum(1 for row in rows if row["is_enabled"] and row["status"] == "active"),
        builtin_count=sum(1 for row in rows if row["is_builtin"]),
    )


@router.get("/effective/{content_platform}", response_model=EffectivePlatformCapabilityResponse)
async def get_effective_platform_capabilities(
    content_platform: str,
    db: AsyncSession = Depends(get_db),
) -> EffectivePlatformCapabilityResponse:
    payload = await platform_capability_service.get_effective_capabilities(content_platform, db)
    return EffectivePlatformCapabilityResponse(**payload)


@router.post("", response_model=PlatformCapabilityResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_capability(
    req: PlatformCapabilityCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> PlatformCapabilityResponse:
    try:
        row = await platform_capability_service.create_capability(req.model_dump(), db)
        await db.commit()
        return PlatformCapabilityResponse(**row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{capability_id}", response_model=PlatformCapabilityResponse)
async def update_platform_capability(
    capability_id: str,
    req: PlatformCapabilityUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> PlatformCapabilityResponse:
    try:
        row = await platform_capability_service.update_capability(
            capability_id,
            req.model_dump(exclude_unset=True),
            db,
        )
        await db.commit()
        return PlatformCapabilityResponse(**row)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"capability not found: {capability_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{capability_id}", response_model=PlatformCapabilityResponse)
async def delete_platform_capability(
    capability_id: str,
    db: AsyncSession = Depends(get_db),
) -> PlatformCapabilityResponse:
    try:
        row = await platform_capability_service.delete_capability(capability_id, db)
        await db.commit()
        return PlatformCapabilityResponse(**row)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"capability not found: {capability_id}")


@router.post("/{capability_id}/restore", response_model=PlatformCapabilityResponse)
async def restore_platform_capability(
    capability_id: str,
    db: AsyncSession = Depends(get_db),
) -> PlatformCapabilityResponse:
    try:
        row = await platform_capability_service.restore_capability(capability_id, db)
        await db.commit()
        return PlatformCapabilityResponse(**row)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"capability not found: {capability_id}")
