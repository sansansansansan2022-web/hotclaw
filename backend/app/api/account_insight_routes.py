"""Account insight snapshot APIs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.account_insight import AccountInsightSnapshotResponse
from app.services.account_analysis_service import account_analysis_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts/{account_id}/insights", tags=["account-insights"])


@router.get("", response_model=AccountInsightSnapshotResponse)
async def get_account_insight(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        snapshot = await account_analysis_service.get_or_refresh_snapshot(account_id, db)
        await db.commit()
        return AccountInsightSnapshotResponse(**account_analysis_service.serialize_snapshot(snapshot))
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception as exc:
        logger.error("account_insight_get_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to load account insight")


@router.post("/refresh", response_model=AccountInsightSnapshotResponse)
async def refresh_account_insight(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        snapshot = await account_analysis_service.refresh_snapshot(account_id, db)
        await db.commit()
        return AccountInsightSnapshotResponse(**account_analysis_service.serialize_snapshot(snapshot))
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message)
    except Exception as exc:
        logger.error("account_insight_refresh_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to refresh account insight")
