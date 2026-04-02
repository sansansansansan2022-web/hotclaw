"""Publish Record Service.

【发布记录服务】
统一管理所有发布记录的生命周期：
- 创建发布记录
- 更新发布状态
- 记录错误
- 状态回查
- 关联草稿和账号状态
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.wechat_config import WeChatPublishRecordModel
from app.models.tables import ArticleDraftModel

logger = get_logger(__name__)


class PublishRecordError(Exception):
    """Publish record operation error."""
    pass


class PublishRecordService:
    """
    Publish Record Service - unified publish record management.

    职责：
    1. 创建发布记录
    2. 更新发布状态
    3. 记录错误信息
    4. 状态回查同步
    5. 查询草稿/账号的发布记录
    """

    # 发布状态常量
    STATUS_PENDING = "pending"
    STATUS_PUBLISHING = "publishing"
    STATUS_PUBLISHED = "published"
    STATUS_FAILED = "failed"
    STATUS_UNKNOWN = "unknown"

    # 触发类型常量
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
        trigger_type: str = "manual_confirm",
        request_snapshot: str | None = None,
        parent_record_id: int | None = None,
    ) -> WeChatPublishRecordModel:
        """
        Create a new publish record.

        Args:
            draft_id: Draft ID
            account_id: Account ID
            db: Database session
            task_id: Task ID (optional)
            source_mode: manual/semi_auto/full_auto
            trigger_type: manual_confirm/semi_auto_confirm/full_auto/auto_retry/manual_retry
            request_snapshot: Request summary (e.g., title)
            parent_record_id: Parent record ID for retry

        Returns:
            Created WeChatPublishRecordModel
        """
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

        logger.info(
            "publish_record_created",
            record_id=record.id,
            draft_id=draft_id,
            trigger_type=trigger_type,
            source_mode=source_mode
        )

        return record

    async def update_success(
        self,
        record_id: int,
        db: AsyncSession,
        wechat_draft_id: str | None = None,
        media_id: str | None = None,
        publish_id: str | None = None,
        article_id: str | None = None,
        url: str | None = None,
        response_snapshot: str | None = None,
    ) -> WeChatPublishRecordModel:
        """
        Update record on successful publish.

        Args:
            record_id: Publish record ID
            db: Database session
            wechat_draft_id: WeChat draft media_id
            media_id: Media ID
            publish_id: Publish job ID
            article_id: Article ID
            url: Published article URL
            response_snapshot: Response summary

        Returns:
            Updated WeChatPublishRecordModel
        """
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.id == record_id
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise PublishRecordError(f"Publish record {record_id} not found")

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

        logger.info(
            "publish_record_success",
            record_id=record_id,
            draft_id=record.draft_id,
            publish_id=publish_id
        )

        return record

    async def update_failed(
        self,
        record_id: int,
        db: AsyncSession,
        error_code: str | None = None,
        error_message: str | None = None,
        response_snapshot: str | None = None,
        keep_status: bool = False,
    ) -> WeChatPublishRecordModel:
        """
        Update record on failed publish.

        Args:
            record_id: Publish record ID
            db: Database session
            error_code: Error code
            error_message: Error message
            response_snapshot: Response summary
            keep_status: If True, don't change status to failed (for retry scenarios)

        Returns:
            Updated WeChatPublishRecordModel
        """
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.id == record_id
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise PublishRecordError(f"Publish record {record_id} not found")

        if not keep_status:
            record.publish_status = self.STATUS_FAILED

        record.finished_at = datetime.now(timezone.utc)
        record.last_checked_at = datetime.now(timezone.utc)
        record.error_code = error_code
        record.error_message = error_message
        record.response_snapshot = response_snapshot

        db.add(record)
        await db.flush()

        logger.warning(
            "publish_record_failed",
            record_id=record_id,
            draft_id=record.draft_id,
            error_code=error_code,
            error_message=error_message
        )

        return record

    async def update_status(
        self,
        record_id: int,
        db: AsyncSession,
        status: str,
        **kwargs: Any,
    ) -> WeChatPublishRecordModel:
        """
        Update record status.

        Args:
            record_id: Publish record ID
            db: Database session
            status: New status
            **kwargs: Additional fields to update

        Returns:
            Updated WeChatPublishRecordModel
        """
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.id == record_id
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise PublishRecordError(f"Publish record {record_id} not found")

        record.publish_status = status
        record.last_checked_at = datetime.now(timezone.utc)

        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)

        db.add(record)
        await db.flush()

        return record

    async def increment_retry(self, record_id: int, db: AsyncSession) -> WeChatPublishRecordModel:
        """
        Increment retry count and create new attempt record.

        Args:
            record_id: Original publish record ID
            db: Database session

        Returns:
            New WeChatPublishRecordModel for retry
        """
        # Get original record
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.id == record_id
        )
        result = await db.execute(stmt)
        original = result.scalar_one_or_none()

        if not original:
            raise PublishRecordError(f"Publish record {record_id} not found")

        if original.publish_status not in {self.STATUS_FAILED, self.STATUS_UNKNOWN}:
            raise PublishRecordError(
                f"Cannot retry record {record_id} with status '{original.publish_status}'"
            )

        # Create new record for retry
        new_record = WeChatPublishRecordModel(
            draft_id=original.draft_id,
            task_id=original.task_id,
            account_id=original.account_id,
            source_mode=original.source_mode,
            trigger_type=self.TRIGGER_MANUAL_RETRY if original.trigger_type in {
                self.TRIGGER_MANUAL_CONFIRM, self.TRIGGER_SEMI_AUTO_CONFIRM
            } else self.TRIGGER_AUTO_RETRY,
            publish_status=self.STATUS_PENDING,
            publish_attempt=original.publish_attempt + 1,
            retry_count=original.retry_count + 1,
            request_snapshot=original.request_snapshot,
            parent_record_id=record_id,
            started_at=datetime.now(timezone.utc),
        )
        db.add(new_record)
        await db.flush()

        logger.info(
            "publish_record_retry_created",
            original_record_id=record_id,
            new_record_id=new_record.id,
            retry_count=new_record.retry_count
        )

        return new_record

    async def get_record(self, record_id: int, db: AsyncSession) -> WeChatPublishRecordModel | None:
        """Get publish record by ID."""
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.id == record_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_draft(
        self, draft_id: int, db: AsyncSession
    ) -> WeChatPublishRecordModel | None:
        """Get latest publish record for a draft."""
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.draft_id == draft_id
        ).order_by(desc(WeChatPublishRecordModel.created_at))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_account(
        self, account_id: str, db: AsyncSession, limit: int = 5
    ) -> list[WeChatPublishRecordModel]:
        """Get latest publish records for an account."""
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.account_id == account_id
        ).order_by(desc(WeChatPublishRecordModel.created_at)).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_records_for_draft(
        self, draft_id: int, db: AsyncSession
    ) -> list[WeChatPublishRecordModel]:
        """Get all publish records for a draft (including retries)."""
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.draft_id == draft_id
        ).order_by(desc(WeChatPublishRecordModel.created_at))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def has_active_publishing(
        self, draft_id: int, db: AsyncSession
    ) -> bool:
        """Check if draft has an active publishing record (pending/publishing)."""
        stmt = select(WeChatPublishRecordModel).where(
            WeChatPublishRecordModel.draft_id == draft_id,
            WeChatPublishRecordModel.publish_status.in_([
                self.STATUS_PENDING, self.STATUS_PUBLISHING
            ])
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def sync_draft_status(
        self, draft_id: int, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Sync draft status from latest publish record.

        Updates draft.publish_status, draft.publish_error_message, draft.published_at.

        Args:
            draft_id: Draft ID
            db: Database session

        Returns:
            dict with updated fields
        """
        stmt = select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id)
        result = await db.execute(stmt)
        draft = result.scalar_one_or_none()

        if not draft:
            raise PublishRecordError(f"Draft {draft_id} not found")

        latest = await self.get_latest_for_draft(draft_id, db)

        if not latest:
            return {"synced": False, "reason": "no_record"}

        now = datetime.now(timezone.utc)

        # Sync from latest record
        if latest.publish_status == self.STATUS_PUBLISHED:
            draft.publish_status = self.STATUS_PUBLISHED
            draft.published_at = latest.published_at or now
            draft.publish_error_message = None
            draft.draft_status = "published"
        elif latest.publish_status == self.STATUS_FAILED:
            draft.publish_status = self.STATUS_FAILED
            draft.publish_error_message = latest.error_message
        elif latest.publish_status in {self.STATUS_PENDING, self.STATUS_PUBLISHING}:
            draft.publish_status = self.STATUS_PUBLISHING
        else:
            draft.publish_status = self.STATUS_UNKNOWN
            draft.publish_error_message = "Unknown publish status"

        db.add(draft)
        await db.flush()

        logger.info(
            "draft_status_synced",
            draft_id=draft_id,
            new_status=draft.publish_status
        )

        return {
            "synced": True,
            "draft_id": draft_id,
            "new_publish_status": draft.publish_status,
            "error_message": draft.publish_error_message,
            "published_at": draft.published_at.isoformat() if draft.published_at else None
        }


publish_record_service = PublishRecordService()
