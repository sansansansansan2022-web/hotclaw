"""Account API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.exceptions import (
    AccountNotFoundError,
    AccountInactiveError,
    AccountValidationError,
    TaskAlreadyExistsError,
    TaskCreateError,
)
from app.core.logger import get_logger
from app.schemas.account import (
    AccountCreateRequest,
    AccountUpdateRequest,
    AccountSummary,
    AccountDetail,
    AccountCreateData,
    AccountRunData,
    AccountListResponse,
)
from app.services.account_service import account_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.post("", response_model=AccountCreateData, status_code=201)
async def create_account(
    req: AccountCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new account."""
    try:
        data = req.model_dump()
        account = await account_service.create_account(data, db)
        await db.commit()
        return AccountCreateData(
            account_id=account.id,
            name=account.name,
            is_active=account.is_active,
            operation_mode=account.operation_mode,
        )
    except AccountValidationError as e:
        logger.warning("account_create_validation_error", error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error("account_create_error", error=str(e))
        raise HTTPException(status_code=500, detail="failed to create account")


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all accounts with pagination."""
    try:
        accounts, total = await account_service.list_accounts(db, page=page, page_size=page_size)
        return AccountListResponse(
            accounts=[
                AccountSummary(
                    account_id=a.id,
                    name=a.name,
                    category=a.category,
                    positioning=a.positioning,
                    operation_mode=a.operation_mode,
                    posting_frequency=a.posting_frequency,
                    auto_run_enabled=a.auto_run_enabled,
                    is_active=a.is_active,
                    last_run_at=a.last_run_at,
                    next_run_at=a.next_run_at,
                    last_run_status=a.last_run_status,
                    last_error_message=a.last_error_message,
                    created_at=a.created_at,
                )
                for a in accounts
            ],
            pagination={
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        )
    except Exception as e:
        logger.error("account_list_error", error=str(e))
        raise HTTPException(status_code=500, detail="failed to load accounts")


@router.get("/{account_id}", response_model=AccountDetail)
async def get_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get account detail with recent tasks."""
    try:
        detail = await account_service.get_account_detail(account_id, db)
        # Parse datetime strings back for pydantic
        from datetime import datetime
        for dt_field in ["last_run_at", "next_run_at", "created_at", "updated_at"]:
            if detail.get(dt_field):
                detail[dt_field] = datetime.fromisoformat(detail[dt_field])
        for t in detail["recent_tasks"]:
            if t.get("created_at"):
                t["created_at"] = datetime.fromisoformat(t["created_at"])
        return AccountDetail(**detail)
    except AccountNotFoundError as e:
        logger.warning("account_get_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error("account_get_error", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="failed to load account")


@router.patch("/{account_id}", response_model=AccountSummary)
async def update_account(
    account_id: str,
    req: AccountUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update account fields."""
    try:
        data = req.model_dump(exclude_unset=True)
        account = await account_service.update_account(account_id, data, db)
        await db.commit()
        return AccountSummary(
            account_id=account.id,
            name=account.name,
            category=account.category,
            positioning=account.positioning,
            operation_mode=account.operation_mode,
            posting_frequency=account.posting_frequency,
            auto_run_enabled=account.auto_run_enabled,
            is_active=account.is_active,
            last_run_at=account.last_run_at,
            next_run_at=account.next_run_at,
            last_run_status=account.last_run_status,
            last_error_message=account.last_error_message,
            created_at=account.created_at,
        )
    except AccountNotFoundError as e:
        logger.warning("account_update_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=e.message)
    except AccountValidationError as e:
        logger.warning("account_update_validation_error", account_id=account_id, error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        logger.error("account_update_error", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="failed to update account")


@router.post("/{account_id}/run", response_model=AccountRunData)
async def run_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a task for the account.

    This endpoint is for manual triggers (e.g., button click).
    For auto-scheduled runs, use the scheduler.

    Returns:
        - 200: Task created successfully
        - 400: Account inactive, positioning missing, or task already running
        - 404: Account not found
        - 500: Internal error
    """
    try:
        account, task = await account_service.run_account(account_id, db, allow_auto=False)
        await db.commit()
        return AccountRunData(
            account_id=account.id,
            task_id=task.id,
            status=task.status,
            operation_mode=account.operation_mode,
        )
    except AccountNotFoundError as e:
        logger.warning("account_run_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=e.message)
    except AccountInactiveError as e:
        logger.warning("account_run_inactive", account_id=account_id)
        raise HTTPException(status_code=400, detail=e.message)
    except AccountValidationError as e:
        logger.warning("account_run_validation_error", account_id=account_id, error=e.message)
        raise HTTPException(status_code=400, detail=e.message)
    except TaskAlreadyExistsError as e:
        logger.warning("account_run_already_running", account_id=account_id)
        raise HTTPException(status_code=409, detail=e.message)
    except TaskCreateError as e:
        logger.error("account_run_task_create_error", account_id=account_id, error=e.message)
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logger.error("account_run_error", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="failed to trigger account run")


@router.post("/{account_id}/enable", response_model=AccountSummary)
async def enable_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Enable an account."""
    try:
        account = await account_service.enable_account(account_id, db)
        await db.commit()
        return AccountSummary(
            account_id=account.id,
            name=account.name,
            category=account.category,
            positioning=account.positioning,
            operation_mode=account.operation_mode,
            posting_frequency=account.posting_frequency,
            auto_run_enabled=account.auto_run_enabled,
            is_active=account.is_active,
            last_run_at=account.last_run_at,
            next_run_at=account.next_run_at,
            last_run_status=account.last_run_status,
            last_error_message=account.last_error_message,
            created_at=account.created_at,
        )
    except AccountNotFoundError as e:
        logger.warning("account_enable_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error("account_enable_error", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="failed to enable account")


@router.post("/{account_id}/disable", response_model=AccountSummary)
async def disable_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Disable an account."""
    try:
        account = await account_service.disable_account(account_id, db)
        return AccountSummary(
            account_id=account.id,
            name=account.name,
            category=account.category,
            positioning=account.positioning,
            operation_mode=account.operation_mode,
            posting_frequency=account.posting_frequency,
            auto_run_enabled=account.auto_run_enabled,
            is_active=account.is_active,
            last_run_at=account.last_run_at,
            next_run_at=account.next_run_at,
            last_run_status=account.last_run_status,
            last_error_message=account.last_error_message,
            created_at=account.created_at,
        )
    except AccountNotFoundError as e:
        logger.warning("account_disable_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error("account_disable_error", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="failed to disable account")
