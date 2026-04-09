"""Account-scoped automation plan APIs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.automation_plan import (
    AutomationPlanCreateRequest,
    AutomationPlanResponse,
    AutomationPlanSummary,
    AutomationPlanUpdateRequest,
)
from app.services.automation_plan_service import automation_plan_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts/{account_id}/automation-plan", tags=["automation-plan"])


def _to_response(summary: dict) -> AutomationPlanSummary:
    return AutomationPlanSummary(**summary)


@router.get("", response_model=AutomationPlanSummary)
async def get_automation_plan(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    account = await automation_plan_service.get_account(account_id, db)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account not found: {account_id}")

    try:
        summary = await automation_plan_service.get_effective_summary(account, db)
        return _to_response(summary)
    except Exception as exc:
        logger.error("automation_plan_get_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to load automation plan")


@router.post("", response_model=AutomationPlanResponse, status_code=201)
async def create_automation_plan(
    account_id: str,
    req: AutomationPlanCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    account = await automation_plan_service.get_account(account_id, db)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account not found: {account_id}")

    try:
        plan = await automation_plan_service.create_initial_plan(account, db, req.model_dump())
        await db.commit()
        return AutomationPlanResponse(**(await automation_plan_service.get_effective_summary(account, db)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("automation_plan_create_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to create automation plan")


@router.patch("", response_model=AutomationPlanResponse)
async def update_automation_plan(
    account_id: str,
    req: AutomationPlanUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    account = await automation_plan_service.get_account(account_id, db)
    if account is None:
        raise HTTPException(status_code=404, detail=f"account not found: {account_id}")

    try:
        await automation_plan_service.upsert_plan(account, req.model_dump(exclude_unset=True), db)
        await db.commit()
        return AutomationPlanResponse(**(await automation_plan_service.get_effective_summary(account, db)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("automation_plan_update_error", account_id=account_id, error=str(exc))
        raise HTTPException(status_code=500, detail="failed to update automation plan")
