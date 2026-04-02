"""WeChat configuration API routes."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.wechat_config import WeChatConfigModel, WeChatPublishRecordModel
from app.models.tables import AccountModel
from app.schemas.wechat import (
    WeChatConfigCreate,
    WeChatConfigUpdate,
    WeChatConfigSummary,
    WeChatConfigDetail,
    WeChatTestConnectionRequest,
    WeChatTestConnectionResponse,
)
from app.services.wechat_token_service import wechat_token_service, WeChatTokenError
from app.services.wechat_publish_service import wechat_publish_service, WeChatPublishError
from app.services.publish_record_service import publish_record_service
from app.core.logger import get_logger

router = APIRouter(prefix="/api/v1/wechat", tags=["wechat"])
logger = get_logger(__name__)


def mask_app_id(app_id: str) -> str:
    """Mask app_id for security."""
    if len(app_id) > 8:
        return app_id[:4] + "****" + app_id[-4:]
    return "****"


@router.get("/config/{account_id}")
async def get_wechat_config(
    account_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get WeChat config for an account.

    Returns masked sensitive data.
    """
    stmt = select(WeChatConfigModel).where(
        WeChatConfigModel.account_id == account_id
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail=f"WeChat config not found for account {account_id}")

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "account_id": config.account_id,
            "app_id_masked": mask_app_id(config.app_id),
            "has_app_secret": bool(config.app_secret),
            "default_author": config.default_author,
            "default_thumb_media_id": config.default_thumb_media_id,
            "need_open_comment": config.need_open_comment,
            "only_fans_can_comment": config.only_fans_can_comment,
            "is_enabled": config.is_enabled,
            "test_status": config.test_status,
            "test_message": config.test_message,
            "last_sync_at": config.last_sync_at.isoformat() if config.last_sync_at else None,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }
    }


@router.post("/config")
async def create_wechat_config(
    request: WeChatConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create WeChat config for an account.
    """
    # Check account exists
    stmt = select(AccountModel).where(AccountModel.id == request.account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail=f"Account {request.account_id} not found")

    # Check if config already exists
    stmt = select(WeChatConfigModel).where(
        WeChatConfigModel.account_id == request.account_id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"WeChat config already exists for account {request.account_id}. Use PUT to update."
        )

    # Create config
    config = WeChatConfigModel(
        account_id=request.account_id,
        app_id=request.app_id,
        app_secret=request.app_secret,
        default_author=request.default_author,
        default_thumb_media_id=request.default_thumb_media_id,
        need_open_comment=request.need_open_comment,
        only_fans_can_comment=request.only_fans_can_comment,
        is_enabled=request.is_enabled,
    )
    db.add(config)
    await db.commit()

    logger.info("wechat_config_created", account_id=request.account_id)

    return {
        "code": 0,
        "message": "WeChat config created",
        "data": {
            "account_id": config.account_id,
            "app_id_masked": mask_app_id(config.app_id),
            "has_app_secret": True,
            "is_enabled": config.is_enabled,
        }
    }


@router.put("/config/{account_id}")
async def update_wechat_config(
    account_id: str,
    request: WeChatConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update WeChat config for an account.
    """
    stmt = select(WeChatConfigModel).where(
        WeChatConfigModel.account_id == account_id
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail=f"WeChat config not found for account {account_id}")

    # Update fields
    if request.app_id is not None:
        config.app_id = request.app_id
    if request.app_secret is not None:
        config.app_secret = request.app_secret
    if request.default_author is not None:
        config.default_author = request.default_author
    if request.default_thumb_media_id is not None:
        config.default_thumb_media_id = request.default_thumb_media_id
    if request.need_open_comment is not None:
        config.need_open_comment = request.need_open_comment
    if request.only_fans_can_comment is not None:
        config.only_fans_can_comment = request.only_fans_can_comment
    if request.is_enabled is not None:
        config.is_enabled = request.is_enabled

    await db.commit()

    logger.info("wechat_config_updated", account_id=account_id)

    return {
        "code": 0,
        "message": "WeChat config updated",
        "data": {
            "account_id": config.account_id,
            "app_id_masked": mask_app_id(config.app_id),
            "has_app_secret": bool(config.app_secret),
            "is_enabled": config.is_enabled,
        }
    }


@router.post("/test-connection")
async def test_wechat_connection(
    request: WeChatTestConnectionRequest
):
    """
    Test WeChat API connection with provided credentials.
    """
    success, message = await wechat_token_service.test_connection(
        request.app_id,
        request.app_secret
    )

    return {
        "code": 0 if success else 1,
        "message": "ok",
        "data": {
            "success": success,
            "message": message
        }
    }


@router.get("/publish-records/{record_id}")
async def get_publish_record(
    record_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single publish record by ID.
    """
    record = await publish_record_service.get_record(record_id, db)

    if not record:
        raise HTTPException(status_code=404, detail=f"Publish record {record_id} not found")

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "id": record.id,
            "draft_id": record.draft_id,
            "task_id": record.task_id,
            "account_id": record.account_id,
            "wechat_draft_id": record.wechat_draft_id,
            "media_id": record.media_id,
            "publish_id": record.publish_id,
            "article_id": record.article_id,
            "url": record.url,
            "publish_status": record.publish_status,
            "source_mode": record.source_mode,
            "trigger_type": record.trigger_type,
            "publish_attempt": record.publish_attempt,
            "retry_count": record.retry_count,
            "error_code": record.error_code,
            "error_message": record.error_message,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
            "published_at": record.published_at.isoformat() if record.published_at else None,
            "last_checked_at": record.last_checked_at.isoformat() if record.last_checked_at else None,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
    }


@router.post("/publish-records/{record_id}/refresh-status")
async def refresh_publish_status(
    record_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh publish status from WeChat API.

    Syncs the latest status from WeChat to local record and draft.
    """
    record = await publish_record_service.get_record(record_id, db)

    if not record:
        raise HTTPException(status_code=404, detail=f"Publish record {record_id} not found")

    if not record.publish_id:
        raise HTTPException(
            status_code=400,
            detail=f"Publish record {record_id} has no publish_id, cannot refresh"
        )

    # Get WeChat config
    stmt = select(WeChatConfigModel).where(
        WeChatConfigModel.account_id == record.account_id
    )
    result = await db.execute(stmt)
    wechat_config = result.scalar_one_or_none()

    if not wechat_config:
        raise HTTPException(
            status_code=400,
            detail=f"WeChat config not found for account {record.account_id}"
        )

    try:
        # Query WeChat publish status
        status_result = await wechat_publish_service.get_publish_status(
            app_id=wechat_config.app_id,
            app_secret=wechat_config.app_secret,
            publish_id=record.publish_id
        )

        # Update local record
        new_status = status_result.get("status", "unknown")

        if new_status == "success":
            await publish_record_service.update_status(
                record_id=record_id,
                db=db,
                status="published",
                article_id=status_result.get("article_id"),
                last_checked_at=datetime.now(timezone.utc),
            )
            # Sync draft status
            await publish_record_service.sync_draft_status(record.draft_id, db)
        elif new_status == "failed":
            await publish_record_service.update_status(
                record_id=record_id,
                db=db,
                status="failed",
                last_checked_at=datetime.now(timezone.utc),
            )
            await publish_record_service.sync_draft_status(record.draft_id, db)
        else:
            # Still pending
            await publish_record_service.update_status(
                record_id=record_id,
                db=db,
                status="publishing",
                last_checked_at=datetime.now(timezone.utc),
            )

        await db.commit()

        # Get updated record
        updated = await publish_record_service.get_record(record_id, db)

        return {
            "code": 0,
            "message": "ok",
            "data": {
                "record_id": record_id,
                "previous_status": record.publish_status,
                "new_status": updated.publish_status if updated else new_status,
                "synced_draft": True,
                "message": f"Status refreshed: {new_status}"
            }
        }

    except WeChatPublishError as e:
        logger.error(
            "refresh_publish_status_failed",
            record_id=record_id,
            error=str(e)
        )
        raise HTTPException(status_code=502, detail=f"WeChat API error: {str(e)}")
    except Exception as e:
        logger.error(
            "refresh_publish_status_error",
            record_id=record_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
