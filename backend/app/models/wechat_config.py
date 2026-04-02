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
    """WeChat publish records for tracking real publishing status."""
    __tablename__ = "wechat_publish_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    wechat_draft_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    media_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publish_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    article_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual_confirm")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
