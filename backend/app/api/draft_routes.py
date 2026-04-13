"""
Draft 草稿箱 API 路由

【草稿箱 API 路由】
提供内容草稿的查询、审核、发布和废弃等功能。

联动模块：
- Service: app.services.draft_service (草稿业务逻辑)
- Schema: app.schemas.draft (请求/响应序列化)
- Exception: app.core.exceptions (Draft 相关异常)

草稿状态机：
- draft: 初始草稿状态（manual 模式任务完成后）
- pending_review: 待审核状态（semi_auto 模式任务完成后）
- approved: 已批准状态（确认发布后）
- rejected: 已拒绝状态（审核未通过）
- discarded: 已废弃状态（手动废弃）

API 端点：
- GET    /api/v1/drafts                    草稿列表（分页、筛选）
- GET    /api/v1/drafts/pending-count       待审核数量统计
- GET    /api/v1/drafts/{id}                草稿详情
- POST   /api/v1/drafts/{id}/confirm-publish  确认发布
- POST   /api/v1/drafts/{id}/discard        废弃草稿
- POST   /api/v1/drafts/{id}/reject         拒绝草稿
- POST   /api/v1/drafts/{id}/rerun          从草稿重跑
- POST   /api/v1/drafts/{id}/publish-to-wechat  发布到微信公众号
- GET    /api/v1/drafts/{id}/wechat-status  微信公众号发布状态
- GET    /api/v1/drafts/{id}/publish-records  发布记录列表
- POST   /api/v1/drafts/{id}/retry-publish  重试发布

调用方：
- 前端: frontend/app/drafts/* (草稿箱页面)
- 前端: frontend/app/accounts/[id]/page.tsx (账号详情页草稿入口)
"""

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse
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
from app.schemas.wechat import PublishToWeChatRequest
from app.services.draft_service import draft_service
from app.services.publish_decision_service import PublishDecisionError
from app.services.publish_record_service import publish_record_service, PublishRecordError

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])


def _json_error(status_code: int, code: int, message: str, data: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": data,
        },
    )


@router.get("", response_model=DraftListResponse)
async def list_drafts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_id: str | None = Query(None),
    draft_status: str | None = Query(None),
    publish_status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    【草稿列表查询】

    分页查询草稿列表，支持多维度筛选。

    查询参数：
    - page: 页码（从 1 开始）
    - page_size: 每页数量（最大 100）
    - account_id: 按账号 ID 筛选（可选）
    - draft_status: 按草稿状态筛选（可选，如 pending_review）
    - publish_status: 按发布状态筛选（可选，如 published）

    调用方：
    - 前端: frontend/app/drafts/page.tsx (草稿箱列表页)
    - 前端: frontend/app/accounts/[id]/page.tsx (账号详情页草稿入口)
    """
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

    State transition: pending_review/draft -> approved
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
    【废弃草稿】

    手动废弃不需要的草稿，将草稿状态从 pending_review 转为 discarded。

    状态转换：
    - pending_review -> discarded

    注意：已发布的草稿不能废弃

    调用方：
    - 前端: frontend/app/drafts/[id]/page.tsx (详情页废弃按钮)

    异常：
    - DraftNotFoundError: 草稿不存在
    - DraftInvalidStatusError: 草稿状态不允许此操作
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


@router.post("/{draft_id}/publish-to-wechat")
async def publish_draft_to_wechat(
    draft_id: int,
    payload: PublishToWeChatRequest | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish draft to WeChat official account.

    This endpoint:
    1. Validates publish conditions
    2. Calls real WeChat API
    3. Updates draft status

    If WeChat config is not set up, returns 400 error.
    If publish fails, draft status is updated with error message.
    """
    try:
        request = payload or PublishToWeChatRequest()
        draft, result = await draft_service.publish_to_wechat(
            draft_id,
            db,
            confirmed_by=request.operator,
            source_mode="manual",
            trigger_type=request.trigger_type or "manual_confirm",
        )
        await db.commit()

        return {
            "code": 0,
            "message": "WeChat publish submitted",
            "data": {
                "draft_id": draft.id,
                "draft_status": draft.draft_status,
                "publish_status": draft.publish_status,
                "published_at": draft.published_at.isoformat() if draft.published_at else None,
                "wechat_media_id": result.get("media_id"),
                "wechat_publish_id": result.get("publish_id"),
                "publish_record_id": result.get("publish_record_id"),
                "decision": result.get("decision"),
                "simulated": result.get("simulated", False),
                "simulation_source": result.get("simulation_source"),
                "provider": result.get("provider"),
            }
        }
    except PublishDecisionError as e:
        logger.warning("draft_wechat_publish_blocked", draft_id=draft_id, error=e.message, reason_code=e.reason_code)
        await db.rollback()
        return _json_error(
            status.HTTP_409_CONFLICT,
            9004,
            e.message,
            {
                "draft_id": draft_id,
                "publish_status": "failed",
                "reason_code": e.reason_code,
                "decision": e.decision,
            },
        )
    except DraftPublishError as e:
        logger.error("draft_wechat_publish_error", draft_id=draft_id, error=e.message)
        await db.commit()
        return _json_error(
            status.HTTP_502_BAD_GATEWAY,
            9004,
            e.message,
            {
                "draft_id": draft_id,
                "publish_status": "failed",
                "error": str(e),
            },
        )
    except Exception as e:
        logger.error("draft_wechat_publish_unexpected_error", draft_id=draft_id, error=str(e))
        await db.rollback()
        return _json_error(status.HTTP_500_INTERNAL_SERVER_ERROR, 5000, f"Internal error: {str(e)}")


@router.get("/{draft_id}/wechat-status")
async def get_wechat_publish_status(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get WeChat publish status for a draft.
    """
    try:
        record = await publish_record_service.get_latest_for_draft(draft_id, db)

        if not record:
            return {
                "code": 0,
                "message": "No WeChat publish record found",
                "data": {
                    "has_record": False,
                    "draft_id": draft_id
                }
            }

        simulation_meta = publish_record_service.get_simulation_metadata(record)

        return {
            "code": 0,
            "message": "ok",
            "data": {
                "has_record": True,
                "record_id": record.id,
                "draft_id": record.draft_id,
                "account_id": record.account_id,
                "task_id": record.task_id,
                "wechat_draft_id": record.wechat_draft_id,
                "media_id": record.media_id,
                "publish_id": record.publish_id,
                "article_id": record.article_id,
                "publish_status": record.publish_status,
                "source_mode": record.source_mode,
                "trigger_type": record.trigger_type,
                "publish_attempt": record.publish_attempt,
                "retry_count": record.retry_count,
                "parent_record_id": record.parent_record_id,
                "error_code": record.error_code,
                "error_message": record.error_message,
                "url": record.url,
                "request_snapshot": record.request_snapshot,
                "response_snapshot": record.response_snapshot,
                "simulated": simulation_meta["simulated"],
                "simulation_source": simulation_meta["simulation_source"],
                "provider": simulation_meta["provider"],
                "started_at": record.started_at.isoformat() if record.started_at else None,
                "finished_at": record.finished_at.isoformat() if record.finished_at else None,
                "published_at": record.published_at.isoformat() if record.published_at else None,
                "last_checked_at": record.last_checked_at.isoformat() if record.last_checked_at else None,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
        }
    except Exception as e:
        logger.error("draft_wechat_status_error", draft_id=draft_id, error=str(e))
        raise


@router.get("/{draft_id}/publish-records")
async def list_draft_publish_records(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all publish records for a draft (including retries).
    """
    try:
        records = await publish_record_service.get_records_for_draft(draft_id, db)

        return {
            "code": 0,
            "message": "ok",
            "data": {
                "draft_id": draft_id,
                "total": len(records),
                "records": [
                    {
                        "id": r.id,
                        "draft_id": r.draft_id,
                        "account_id": r.account_id,
                        "task_id": r.task_id,
                        "wechat_draft_id": r.wechat_draft_id,
                        "media_id": r.media_id,
                        "publish_id": r.publish_id,
                        "article_id": r.article_id,
                        "publish_status": r.publish_status,
                        "source_mode": r.source_mode,
                        "trigger_type": r.trigger_type,
                        "publish_attempt": r.publish_attempt,
                        "retry_count": r.retry_count,
                        "parent_record_id": r.parent_record_id,
                        "error_code": r.error_code,
                        "error_message": r.error_message,
                        "url": r.url,
                        "request_snapshot": r.request_snapshot,
                        "response_snapshot": r.response_snapshot,
                        "simulated": publish_record_service.get_simulation_metadata(r)["simulated"],
                        "simulation_source": publish_record_service.get_simulation_metadata(r)["simulation_source"],
                        "provider": publish_record_service.get_simulation_metadata(r)["provider"],
                        "started_at": r.started_at.isoformat() if r.started_at else None,
                        "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None,
                        "published_at": r.published_at.isoformat() if r.published_at else None,
                        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    }
                    for r in records
                ]
            }
        }
    except Exception as e:
        logger.error("draft_publish_records_error", draft_id=draft_id, error=str(e))
        raise


@router.post("/{draft_id}/retry-publish")
async def retry_publish_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    【重试发布草稿】

    重新尝试发布失败的草稿到微信公众号。

    限制条件：
    - 草稿必须有失败的发布记录
    - 重试次数不能超过 3 次

    工作流程：
    1. 验证重试条件
    2. 调用微信公众号 API 重新发布
    3. 更新发布记录

    调用方：
    - 前端: frontend/app/drafts/[id]/page.tsx (详情页重试按钮)

    异常：
    - PublishRecordError: 重试次数超限或状态不允许
    - PublishDecisionError: 发布决策阻止
    - DraftPublishError: 微信 API 调用失败
    """
    try:
        draft, result = await draft_service.retry_publish_to_wechat(draft_id, db)
        await db.commit()

        return {
            "code": 0,
            "message": "Retry publish initiated successfully",
            "data": {
                "draft_id": draft.id,
                "draft_status": draft.draft_status,
                "publish_status": draft.publish_status,
                "published_at": draft.published_at.isoformat() if draft.published_at else None,
                "wechat_media_id": result.get("media_id"),
                "wechat_publish_id": result.get("publish_id"),
                "publish_record_id": result.get("publish_record_id"),
                "simulated": result.get("simulated", False),
                "simulation_source": result.get("simulation_source"),
                "provider": result.get("provider"),
            }
        }
    except PublishRecordError as e:
        logger.warning("draft_retry_publish_record_error", draft_id=draft_id, error=str(e))
        await db.rollback()
        return _json_error(
            status.HTTP_409_CONFLICT,
            9004,
            str(e),
            {
                "draft_id": draft_id,
                "publish_status": "failed",
                "error": str(e),
            },
        )
    except PublishDecisionError as e:
        logger.warning("draft_retry_publish_blocked", draft_id=draft_id, error=e.message, reason_code=e.reason_code)
        await db.rollback()
        return _json_error(
            status.HTTP_409_CONFLICT,
            9004,
            e.message,
            {
                "draft_id": draft_id,
                "publish_status": "failed",
                "reason_code": e.reason_code,
                "decision": e.decision,
            },
        )
    except DraftPublishError as e:
        logger.error("draft_retry_publish_error", draft_id=draft_id, error=e.message)
        await db.commit()
        return _json_error(
            status.HTTP_502_BAD_GATEWAY,
            9004,
            e.message,
            {
                "draft_id": draft_id,
                "publish_status": "failed",
                "error": str(e),
            },
        )
    except Exception as e:
        logger.error("draft_retry_publish_unexpected_error", draft_id=draft_id, error=str(e))
        await db.rollback()
        return _json_error(status.HTTP_500_INTERNAL_SERVER_ERROR, 5000, f"Internal error: {str(e)}")
