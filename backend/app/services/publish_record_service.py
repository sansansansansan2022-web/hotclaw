"""Publish record service for WeChat publish tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import AccountModel, ArticleDraftModel
from app.models.wechat_config import WeChatPublishRecordModel

logger = get_logger(__name__)


class PublishRecordError(Exception):
    """Publish record operation error."""


class PublishRecordService:
    """Create, update, retry, and sync publish records."""

    STATUS_PENDING = "pending"
    STATUS_UPLOADING_MEDIA = "uploading_media"
    STATUS_CREATING_DRAFT = "creating_draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_POLLING = "polling"
    STATUS_PUBLISHING = "publishing"
    STATUS_PUBLISHED = "published"
    STATUS_FAILED = "failed"
    STATUS_UNKNOWN = "unknown"

    ACTIVE_STATUSES = {
        STATUS_PENDING,
        STATUS_UPLOADING_MEDIA,
        STATUS_CREATING_DRAFT,
        STATUS_SUBMITTED,
        STATUS_POLLING,
        STATUS_PUBLISHING,
    }

    TERMINAL_STATUSES = {STATUS_PUBLISHED, STATUS_FAILED, STATUS_UNKNOWN}

    TRIGGER_MANUAL_CONFIRM = "manual_confirm"
    TRIGGER_SEMI_AUTO_CONFIRM = "semi_auto_confirm"
    TRIGGER_FULL_AUTO = "full_auto"
    TRIGGER_AUTO_RETRY = "auto_retry"
    TRIGGER_MANUAL_RETRY = "manual_retry"

    async def create_record(
        self,
        draft_id: int,
        account_id: str,
        db: AsyncSession,
        task_id: str | None = None,
        source_mode: str = "manual",
        trigger_type: str = TRIGGER_MANUAL_CONFIRM,
        request_snapshot: str | None = None,
        parent_record_id: int | None = None,
    ) -> WeChatPublishRecordModel:
        record = WeChatPublishRecordModel(
            draft_id=draft_id,
            task_id=task_id,
            account_id=account_id,
            source_mode=source_mode,
            trigger_type=trigger_type,
            publish_status=self.STATUS_PENDING,
            publish_attempt=1,
            retry_count=0,
            request_snapshot=request_snapshot,
            parent_record_id=parent_record_id,
            started_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()
        logger.info("publish_record_created", record_id=record.id, draft_id=draft_id, account_id=account_id)
        return record

    async def update_success(
        self,
        record_id: int,
        db: AsyncSession,
        *,
        wechat_draft_id: str | None = None,
        media_id: str | None = None,
        publish_id: str | None = None,
        article_id: str | None = None,
        url: str | None = None,
        response_snapshot: str | None = None,
    ) -> WeChatPublishRecordModel:
        record = await self._get_required_record(record_id, db)
        now = datetime.now(timezone.utc)
        record.publish_status = self.STATUS_PUBLISHED
        record.finished_at = now
        record.published_at = now
        record.last_checked_at = now
        record.wechat_draft_id = wechat_draft_id or record.wechat_draft_id
        record.media_id = media_id or record.media_id
        record.publish_id = publish_id or record.publish_id
        record.article_id = article_id or record.article_id
        record.url = url or record.url
        record.response_snapshot = response_snapshot
        record.error_code = None
        record.error_message = None
        db.add(record)
        await db.flush()
        logger.info("publish_record_success", record_id=record_id, draft_id=record.draft_id)
        return record

    async def update_failed(
        self,
        record_id: int,
        db: AsyncSession,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        response_snapshot: str | None = None,
        keep_status: bool = False,
    ) -> WeChatPublishRecordModel:
        record = await self._get_required_record(record_id, db)
        if not keep_status:
            record.publish_status = self.STATUS_FAILED
        record.finished_at = datetime.now(timezone.utc)
        record.last_checked_at = datetime.now(timezone.utc)
        record.error_code = error_code
        record.error_message = error_message
        record.response_snapshot = response_snapshot
        db.add(record)
        await db.flush()
        logger.warning("publish_record_failed", record_id=record_id, error_code=error_code, error=error_message)
        return record

    async def update_status(
        self,
        record_id: int,
        db: AsyncSession,
        *,
        status: str,
        **kwargs: Any,
    ) -> WeChatPublishRecordModel:
        record = await self._get_required_record(record_id, db)
        record.publish_status = status
        record.last_checked_at = datetime.now(timezone.utc)
        if status == self.STATUS_PUBLISHED and not record.published_at:
            record.published_at = datetime.now(timezone.utc)
            record.finished_at = record.published_at
        elif status in {self.STATUS_FAILED, self.STATUS_UNKNOWN}:
            record.finished_at = datetime.now(timezone.utc)
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        db.add(record)
        await db.flush()
        logger.info("publish_record_status_updated", record_id=record_id, status=status)
        return record

    async def increment_retry(self, record_id: int, db: AsyncSession) -> WeChatPublishRecordModel:
        original = await self._get_required_record(record_id, db)
        if original.publish_status not in {self.STATUS_FAILED, self.STATUS_UNKNOWN}:
            raise PublishRecordError(
                f"Cannot retry record {record_id} with status '{original.publish_status}'"
            )

        trigger_type = (
            self.TRIGGER_MANUAL_RETRY
            if original.trigger_type in {self.TRIGGER_MANUAL_CONFIRM, self.TRIGGER_SEMI_AUTO_CONFIRM, self.TRIGGER_MANUAL_RETRY}
            else self.TRIGGER_AUTO_RETRY
        )

        retry_record = WeChatPublishRecordModel(
            draft_id=original.draft_id,
            task_id=original.task_id,
            account_id=original.account_id,
            source_mode=original.source_mode,
            trigger_type=trigger_type,
            publish_status=self.STATUS_PENDING,
            publish_attempt=original.publish_attempt + 1,
            retry_count=original.retry_count + 1,
            request_snapshot=original.request_snapshot,
            parent_record_id=original.id,
            started_at=datetime.now(timezone.utc),
        )
        db.add(retry_record)
        await db.flush()
        logger.info(
            "publish_record_retry_created",
            original_record_id=record_id,
            retry_record_id=retry_record.id,
            retry_count=retry_record.retry_count,
        )
        return retry_record

    async def get_record(self, record_id: int, db: AsyncSession) -> WeChatPublishRecordModel | None:
        result = await db.execute(select(WeChatPublishRecordModel).where(WeChatPublishRecordModel.id == record_id))
        return result.scalar_one_or_none()

    async def get_latest_for_draft(self, draft_id: int, db: AsyncSession) -> WeChatPublishRecordModel | None:
        stmt = (
            select(WeChatPublishRecordModel)
            .where(WeChatPublishRecordModel.draft_id == draft_id)
            .order_by(desc(WeChatPublishRecordModel.created_at))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_account(
        self,
        account_id: str,
        db: AsyncSession,
        limit: int = 5,
    ) -> list[WeChatPublishRecordModel]:
        stmt = (
            select(WeChatPublishRecordModel)
            .where(WeChatPublishRecordModel.account_id == account_id)
            .order_by(desc(WeChatPublishRecordModel.created_at))
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_records_for_draft(self, draft_id: int, db: AsyncSession) -> list[WeChatPublishRecordModel]:
        stmt = (
            select(WeChatPublishRecordModel)
            .where(WeChatPublishRecordModel.draft_id == draft_id)
            .order_by(desc(WeChatPublishRecordModel.created_at))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def has_active_publishing(self, draft_id: int, db: AsyncSession) -> bool:
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.draft_id == draft_id,
            WeChatPublishRecordModel.publish_status.in_(list(self.ACTIVE_STATUSES)),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def sync_draft_status(self, draft_id: int, db: AsyncSession) -> dict[str, Any]:
        draft_result = await db.execute(select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id))
        draft = draft_result.scalar_one_or_none()
        if not draft:
            raise PublishRecordError(f"Draft {draft_id} not found")

        latest = await self.get_latest_for_draft(draft_id, db)
        if not latest:
            return {"synced": False, "reason": "no_record"}

        previous_publish_status = draft.publish_status

        if latest.publish_status == self.STATUS_PUBLISHED:
            draft.publish_status = "published"
            draft.draft_status = "published"
            draft.published_at = latest.published_at or datetime.now(timezone.utc)
            draft.publish_error_message = None
        elif latest.publish_status == self.STATUS_FAILED:
            draft.publish_status = "failed"
            if draft.draft_status == "published":
                draft.draft_status = "approved"
            draft.publish_error_message = latest.error_message
        elif latest.publish_status in self.ACTIVE_STATUSES:
            if draft.draft_status in {"draft", "pending_review"}:
                draft.draft_status = "approved"
            draft.publish_status = "pending"
            draft.publish_error_message = None
        else:
            draft.publish_status = "failed"
            draft.publish_error_message = latest.error_message or "Unknown publish state"

        db.add(draft)
        await db.flush()

        if draft.account_id:
            update_data: dict[str, Any] = {"last_publish_status": latest.publish_status}
            if latest.error_message:
                update_data["last_publish_error_message"] = latest.error_message[:500]
            elif latest.publish_status == self.STATUS_PUBLISHED:
                update_data["last_publish_error_message"] = None
            if latest.publish_status == self.STATUS_PUBLISHED and latest.published_at:
                update_data["last_published_at"] = latest.published_at
            await db.execute(update(AccountModel).where(AccountModel.id == draft.account_id).values(**update_data))

        logger.info(
            "draft_status_synced_from_publish_record",
            draft_id=draft_id,
            previous_status=previous_publish_status,
            new_status=draft.publish_status,
            publish_record_status=latest.publish_status,
        )
        return {
            "synced": True,
            "draft_id": draft_id,
            "previous_publish_status": previous_publish_status,
            "draft_publish_status": draft.publish_status,
            "draft_status": draft.draft_status,
            "record_status": latest.publish_status,
            "published_at": draft.published_at.isoformat() if draft.published_at else None,
        }

    async def _get_required_record(self, record_id: int, db: AsyncSession) -> WeChatPublishRecordModel:
        record = await self.get_record(record_id, db)
        if not record:
            raise PublishRecordError(f"Publish record {record_id} not found")
        return record


publish_record_service = PublishRecordService()
