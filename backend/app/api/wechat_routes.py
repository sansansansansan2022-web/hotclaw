"""WeChat configuration and publish record API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.session import get_db
from app.schemas.wechat import (
    PublishRecordRead,
    PublishRecordStatusSyncResponse,
    WeChatConfigCreate,
    WeChatConfigUpdate,
    WeChatTestConnectionRequest,
)
from app.services.publish_record_service import PublishRecordError, publish_record_service
from app.services.wechat_config_service import (
    WeChatConfigServiceError,
    wechat_config_service,
)
from app.services.wechat_publish_service import WeChatPublishError, wechat_publish_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["wechat"])


def serialize_config(config) -> dict:
    return wechat_config_service.to_read_model(config).model_dump(mode="json")


def serialize_publish_record(record) -> dict:
    simulation_meta = publish_record_service.get_simulation_metadata(record)
    return PublishRecordRead(
        id=record.id,
        draft_id=record.draft_id,
        account_id=record.account_id,
        task_id=record.task_id,
        wechat_draft_media_id=record.wechat_draft_id or record.media_id,
        wechat_publish_id=record.publish_id,
        wechat_article_url=record.url,
        wechat_msg_data_id=record.article_id,
        publish_status=record.publish_status,
        source_mode=record.source_mode,
        trigger_type=record.trigger_type,
        attempt_count=record.publish_attempt,
        retry_count=record.retry_count,
        simulated=simulation_meta["simulated"],
        simulation_source=simulation_meta["simulation_source"],
        provider=simulation_meta["provider"],
        last_error_code=record.error_code,
        last_error_message=record.error_message,
        started_at=record.started_at,
        finished_at=record.finished_at,
        published_at=record.published_at,
        last_checked_at=record.last_checked_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    ).model_dump(mode="json")


def serialize_connection_test_result(result) -> dict:
    message = result.message or ("Connection successful" if result.success else "Connection failed")
    return {
        "code": 0 if result.success else 1,
        "message": message,
        "data": result.model_dump(mode="json"),
    }


@router.get("/accounts/{account_id}/wechat-config")
@router.get("/wechat/config/{account_id}")
async def get_wechat_config(account_id: str, db: AsyncSession = Depends(get_db)):
    try:
        config = await wechat_config_service.get_or_raise(account_id, db)
        return {"code": 0, "message": "ok", "data": serialize_config(config)}
    except WeChatConfigServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/accounts/{account_id}/wechat-config")
async def create_account_wechat_config(
    account_id: str,
    payload: WeChatConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        config = await wechat_config_service.create(account_id, payload, db)
        await db.commit()
        return {"code": 0, "message": "WeChat config created", "data": serialize_config(config)}
    except WeChatConfigServiceError as exc:
        status_code = status.HTTP_409_CONFLICT if "already exists" in str(exc) else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/wechat/config")
async def create_legacy_wechat_config(payload: WeChatConfigCreate, db: AsyncSession = Depends(get_db)):
    if not payload.account_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="account_id is required")
    return await create_account_wechat_config(payload.account_id, payload, db)


@router.put("/accounts/{account_id}/wechat-config")
@router.put("/wechat/config/{account_id}")
async def update_wechat_config(
    account_id: str,
    payload: WeChatConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        config = await wechat_config_service.update(account_id, payload, db)
        await db.commit()
        return {"code": 0, "message": "WeChat config updated", "data": serialize_config(config)}
    except WeChatConfigServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/accounts/{account_id}/wechat-config/test")
async def test_account_wechat_config(account_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await wechat_config_service.test_connection(account_id, db)
        await db.commit()
        return serialize_connection_test_result(result)
    except WeChatConfigServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/wechat/test-connection")
async def test_legacy_wechat_credentials(payload: WeChatTestConnectionRequest):
    result = await wechat_config_service.test_credentials(payload.app_id, payload.app_secret)
    return serialize_connection_test_result(result)


@router.get("/publish-records/{publish_record_id}")
@router.get("/wechat/publish-records/{publish_record_id}")
async def get_publish_record(publish_record_id: int, db: AsyncSession = Depends(get_db)):
    record = await publish_record_service.get_record(publish_record_id, db)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Publish record {publish_record_id} not found")
    return {"code": 0, "message": "ok", "data": serialize_publish_record(record)}


@router.post("/publish-records/{publish_record_id}/sync-status")
async def sync_publish_status(publish_record_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await wechat_publish_service.sync_publish_status(publish_record_id, db)
        await db.commit()
        payload = PublishRecordStatusSyncResponse(**result).model_dump(mode="json")
        return {"code": 0, "message": "ok", "data": payload}
    except PublishRecordError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WeChatPublishError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/wechat/publish-records/{publish_record_id}/refresh-status")
async def refresh_publish_status(publish_record_id: int, db: AsyncSession = Depends(get_db)):
    return await sync_publish_status(publish_record_id, db)
