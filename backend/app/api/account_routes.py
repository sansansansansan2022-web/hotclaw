"""
Account API endpoints.

【账号管理 API 路由】
提供公众号账号的 CRUD 操作和运行控制接口。

联动模块：
- Service: app.services.account_service (业务逻辑)
- Schema: app.schemas.account (请求/响应序列化)
- Exception: app.core.exceptions (AccountNotFoundError, AccountInactiveError 等)

API 端点：
- POST   /api/v1/accounts           创建账号
- GET    /api/v1/accounts           账号列表（分页）
- GET    /api/v1/accounts/{id}      账号详情
- PATCH  /api/v1/accounts/{id}      更新账号
- POST   /api/v1/accounts/{id}/run  手动触发运行
- POST   /api/v1/accounts/{id}/enable  启用账号
- POST   /api/v1/accounts/{id}/disable 禁用账号

调用方：
- 前端: frontend/app/accounts/* (React 页面)
- 前端 API: frontend/lib/api.ts (createAccount, listAccounts 等)
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.tables import AccountModel
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
from app.schemas.common import ApiResponse
from app.services.account_service import account_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])
_background_tasks: dict[str, asyncio.Task] = {}


async def _run_account_task_in_background(task_id: str, account_id: str) -> None:
    """Run an account-created task in a dedicated DB session."""
    from app.db.session import async_session_factory
    from app.core.tracer import set_task_id
    from app.services.task_service import task_service

    async with async_session_factory() as bg_db:
        try:
            set_task_id(task_id)
            logger.info("account_run_background_started", account_id=account_id, task_id=task_id)
            await task_service.run_task(task_id, bg_db)
        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            _background_tasks.pop(task_id, None)


# =============================================================================
# CRUD 操作
# =============================================================================

@router.post("", response_model=AccountCreateData, status_code=201)
async def create_account(
    req: AccountCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    创建新账号。

    调用 account_service.create_account() 创建账号记录。
    成功返回 AccountCreateData（包含 account_id）。

    联动：
    - Service: account_service.create_account()
    - Schema: AccountCreateRequest -> AccountCreateData
    """
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
    """
    账号列表查询（分页）。

    调用 account_service.list_accounts() 获取账号列表。
    支持分页参数 page 和 page_size，默认每页 20 条。

    调用方：
    - 前端: frontend/app/accounts/page.tsx (账号列表页)

    联动：
    - Service: account_service.list_accounts()
    - Schema: AccountSummary -> AccountListResponse
    - 返回 pagination 字段包含 total, total_pages
    """
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
    """
    获取账号详情。

    调用 account_service.get_account_detail() 获取完整账号信息，
    包括基本信息、发布策略、运行状态和最近任务列表。

    调用方：
    - 前端: frontend/app/accounts/[id]/page.tsx (账号详情页)
    - 前端: frontend/app/accounts/[id]/edit/page.tsx (编辑页加载数据)

    联动：
    - Service: account_service.get_account_detail()
    - Schema: AccountDetail
    - 返回包含 recent_tasks 字段（最近 5 条任务）
    """
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
    """
    更新账号字段（部分更新）。

    调用 account_service.update_account() 更新指定字段。
    只更新请求体中提供的字段（exclude_unset=True），未提供的字段保持不变。

    调用方：
    - 前端: frontend/app/accounts/[id]/edit/page.tsx (保存修改)

    联动：
    - Service: account_service.update_account()
    - Schema: AccountUpdateRequest -> AccountSummary
    """
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


# =============================================================================
# 运行控制
# =============================================================================

@router.post("/{account_id}/run", response_model=AccountRunData)
async def run_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    手动触发账号运行。

    【与 Scheduler 触发的区别】
    - 手动触发: allow_auto=False，强制创建新任务（即使有运行中的任务）
    - 自动触发: allow_auto=True，由 Scheduler 调用（会检查防重复）

    此端点用于前端"立即运行"按钮。
    会检查账号状态、positioning 是否存在、是否有运行中任务。

    调用方：
    - 前端: frontend/app/accounts/page.tsx (列表页运行按钮)
    - 前端: frontend/app/accounts/[id]/page.tsx (详情页运行按钮)

    联动：
    - Service: account_service.run_account(allow_auto=False)
    - 创建 TaskModel 记录
    - 任务 ID 通过 AccountRunData 返回，前端可跳转到任务详情页

    异常处理：
    - 404: AccountNotFoundError - 账号不存在
    - 400: AccountInactiveError - 账号已禁用
    - 400: AccountValidationError - positioning 为空
    - 409: TaskAlreadyExistsError - 已有运行中任务（allow_auto=True 时触发）
    - 500: TaskCreateError - 任务创建失败
    """
    try:
        account, task = await account_service.run_account(account_id, db, allow_auto=False)
        await db.commit()
        bg_task = asyncio.create_task(_run_account_task_in_background(task.id, account.id))
        _background_tasks[task.id] = bg_task
        logger.info("account_run_background_scheduled", account_id=account.id, task_id=task.id)
        return AccountRunData(
            account_id=account.id,
            task_id=task.id,
            status=task.status,
            operation_mode=account.operation_mode,
            effective_mode=(
                task.input_data.get("ops_context", {})
                .get("run_strategy", {})
                .get("effective_mode")
                if isinstance(task.input_data, dict)
                else None
            ),
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
    """
    启用账号。

    启用后账号可以被 Scheduler 扫描到（如果 auto_run_enabled=True 且 operation_mode != manual）。

    调用方：
    - 前端: frontend/app/accounts/[id]/page.tsx (详情页启用按钮)

    联动：
    - Service: account_service.enable_account()
    - 更新 is_active=True
    - 更新 last_run_status=None（重置运行状态）
    """
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
    """
    禁用账号。

    禁用后账号不会被 Scheduler 扫描到，也不会出现在定时任务中。
    已运行的任务不受影响。

    调用方：
    - 前端: frontend/app/accounts/[id]/page.tsx (详情页禁用按钮)

    联动：
    - Service: account_service.disable_account()
    - 更新 is_active=False
    """
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


# ---------------------------------------------------------------------------
# Style profile endpoints
# Read / rebuild the account's style_profile_json (written by MemoryCuratorAgent)
# ---------------------------------------------------------------------------


@router.get("/{account_id}/style-profile")
async def get_account_style_profile(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Return the account's style profile.

    Matches frontend `AccountStyleProfileResponse`:
        { account_id, generated_at?, style_profile: StyleProfile | null }

    The `style_profile_json` column is written by `MemoryCuratorAgent` after
    each task and merged incrementally. If not yet generated, returns null.
    """
    result = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")

    style_profile = account.style_profile_json or None
    generated_at = account.last_evolved_at.isoformat() if account.last_evolved_at else None

    return ApiResponse(
        data={
            "account_id": account_id,
            "generated_at": generated_at,
            "style_profile": style_profile,
        }
    )


@router.post("/{account_id}/style-profile/rebuild")
async def rebuild_account_style_profile(
    account_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Reset the style profile so it will be re-accumulated from future tasks.

    This does NOT trigger a rebuild from scratch — it clears `style_profile_json`
    so the next task's MemoryCuratorAgent starts fresh.

    Matches frontend `AccountStyleProfileActionResponse`:
        { account_id, status, message?, generated_at? }
    """
    result = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")

    account.style_profile_json = None
    account.last_evolved_at = None
    db.add(account)
    await db.commit()
    logger.info("style_profile_reset", account_id=account_id)

    return ApiResponse(
        data={
            "account_id": account_id,
            "status": "ok",
            "message": "风格档案已重置，将在下次任务完成后自动重建。",
            "generated_at": None,
        }
    )
