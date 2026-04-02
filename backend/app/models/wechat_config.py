"""WeChat Official Account configuration model."""

from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.tables import Base


class WeChatConfigModel(Base):
    """WeChat Official Account configuration per account."""
    __tablename__ = "wechat_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    app_id: Mapped[str] = mapped_column(String(64), nullable=False)
    app_secret: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    default_author: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_thumb_media_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    need_open_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    only_fans_can_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    test_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WeChatPublishRecordModel(Base):
    """
    WeChat publish records for tracking real publishing status.

    【发布记录表】
    记录每次真实发布尝试的完整生命周期，包括：
    - 发布状态（pending/publishing/published/failed/unknown）
    - 发布来源（manual_confirm/semi_auto_confirm/full_auto/retry）
    - 重试次数和时间
    - 请求/响应快照
    - 错误详情
    """
    __tablename__ = "wechat_publish_records"

    # 基本信息
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # 微信返回的 ID
    wechat_draft_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    media_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publish_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    article_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 发布状态
    publish_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    """状态值: pending/publishing/published/failed/unknown"""

    # 发布来源
    source_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    """来源模式: manual/semi_auto/full_auto"""
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual_confirm")
    """触发类型: manual_confirm/semi_auto_confirm/full_auto/auto_retry/manual_retry"""

    # 重试相关
    publish_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    """第几次发布尝试"""
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """已重试次数"""
    parent_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """父记录 ID（用于关联重试前记录）"""

    # 错误信息
    error_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 请求/响应快照（最小必要字段）
    request_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    """请求摘要，如标题、作者等"""
    response_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    """响应摘要，如错误码、错误信息等"""

    # 时间戳
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    """最近一次状态回查时间"""

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
