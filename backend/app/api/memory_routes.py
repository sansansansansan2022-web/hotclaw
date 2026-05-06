"""Account memory API routes (Phase 1).

Exposes three endpoints under `/api/v1/accounts/{account_id}/article-memories`:

    GET    /                  → paginated/searched list (frontend memory page)
    POST   /rebuild           → drop & re-create all memories from drafts
    POST   /sync              → incremental: only newly-published drafts

Response payloads are wrapped in the project-wide `ApiResponse(envelope)` so the
frontend's `request()` helper unwraps `data` automatically (see
`frontend/lib/api/index.ts` and `frontend/types/index.ts:906-916`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.services.memory_service import memory_service, serialize_memory

router = APIRouter(prefix="/api/v1/accounts", tags=["account-memories"])
logger = get_logger(__name__)


@router.get("/{account_id}/article-memories")
async def list_account_memories(
    account_id: str,
    query: str | None = Query(default=None, description="full-text query"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List article memories for an account.

    Matches `AccountMemoryListResponse` in `frontend/types/index.ts:906-911`:

        { account_id, total, query, memories: ContentMemory[] }
    """
    try:
        memories, total = await memory_service.list_article_memories(
            account_id=account_id,
            query=query,
            page=page,
            page_size=page_size,
            db=db,
        )
    except AccountNotFoundError as exc:
        logger.warning("memory_list_account_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=exc.message)

    return ApiResponse(
        data={
            "account_id": account_id,
            "total": int(total),
            "query": query,
            "memories": [serialize_memory(m) for m in memories],
        }
    )


@router.post("/{account_id}/article-memories/rebuild")
async def rebuild_account_memories(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Wipe + re-distill all memories for an account.

    Matches `AccountMemoryActionResponse`:

        { account_id, status, message?, job_id? }
    """
    try:
        result = await memory_service.rebuild_article_memories(account_id, db)
    except AccountNotFoundError as exc:
        logger.warning("memory_rebuild_account_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=exc.message)

    return ApiResponse(
        data={
            "account_id": account_id,
            "status": "ok",
            "message": result.get("message"),
            "job_id": None,
            "processed": result.get("processed", 0),
            "created": result.get("created", 0),
            "removed": result.get("removed", 0),
        }
    )


@router.post("/{account_id}/article-memories/sync")
async def sync_account_memories(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Incremental: only distill drafts not yet present in memory.

    Matches `AccountMemoryActionResponse`.
    """
    try:
        result = await memory_service.sync_article_memories(account_id, db)
    except AccountNotFoundError as exc:
        logger.warning("memory_sync_account_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=exc.message)

    return ApiResponse(
        data={
            "account_id": account_id,
            "status": "ok",
            "message": result.get("message"),
            "job_id": None,
            "processed": result.get("processed", 0),
            "created": result.get("created", 0),
            "skipped": result.get("skipped", 0),
        }
    )
