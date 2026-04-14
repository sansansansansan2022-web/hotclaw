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
    AccountRunRequest,
    AccountSummary,
    AccountDetail,
    AccountCreateData,
    AccountRunData,
    AccountListResponse,
)
from app.services.account_service import account_service
from app.services.account_run_dispatch_service import account_run_dispatch_service
from app.services.compose_preview_service import compose_preview_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


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
                AccountSummary(**account_service.build_account_summary_payload(a))
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
        return AccountSummary(**account_service.build_account_summary_payload(account))
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
    req: AccountRunRequest | None = None,
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
        # Account remains the workspace/container. This route is the compatibility
        # manual trigger while explicit selection/preview-driven creation is phased in.
        explicit_input = None
        if req and (req.selection_session_id or req.preview_payload or req.creation_note):
            selection_session_id = req.selection_session_id
            preview_payload = req.preview_payload if isinstance(req.preview_payload, dict) else None
            if not selection_session_id:
                raise HTTPException(status_code=400, detail="selection_session_id is required when explicit creation input is provided")

            preview_bundle = await compose_preview_service.build_preview_bundle(
                account_id=account_id,
                selection_session_id=selection_session_id,
                creation_note=req.creation_note,
                preview_payload=preview_payload,
                db=db,
            )
            explicit_input = preview_bundle["runtime_payload"]

        account, task = await account_service.run_account(
            account_id,
            db,
            allow_auto=False,
            explicit_input=explicit_input,
        )
        await db.commit()
        account_run_dispatch_service.schedule(task_id=task.id, account_id=account.id)
        return AccountRunData(
            **account_service.build_account_run_payload(
                account,
                task,
                selection_session_id=(explicit_input or {}).get("selection_session_id")
                if isinstance(explicit_input, dict)
                else None,
            )
        )
    except AccountNotFoundError as e:
        logger.warning("account_run_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=e.message)
    except HTTPException:
        raise
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
        return AccountSummary(**account_service.build_account_summary_payload(account))
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
        await db.commit()
        return AccountSummary(**account_service.build_account_summary_payload(account))
    except AccountNotFoundError as e:
        logger.warning("account_disable_not_found", account_id=account_id)
        raise HTTPException(status_code=404, detail=e.message)
    except Exception as e:
        logger.error("account_disable_error", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail="failed to disable account")
