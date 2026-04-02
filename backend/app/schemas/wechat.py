"""WeChat related Pydantic schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# WeChat Config Schemas
# =============================================================================


class WeChatConfigBase(BaseModel):
    """Base WeChat config schema."""
    app_id: str = Field(..., description="WeChat App ID")
    app_secret: str = Field(..., description="WeChat App Secret (will be masked in response)")
    default_author: str | None = Field(None, description="Default author name")
    default_thumb_media_id: str | None = Field(None, description="Default cover image media_id")
    need_open_comment: bool = Field(True, description="Enable comments")
    only_fans_can_comment: bool = Field(False, description="Only fans can comment")
    is_enabled: bool = Field(True, description="Enable WeChat publishing")


class WeChatConfigCreate(WeChatConfigBase):
    """Schema for creating WeChat config."""
    account_id: str = Field(..., description="Account ID to bind")


class WeChatConfigUpdate(BaseModel):
    """Schema for updating WeChat config."""
    app_id: str | None = Field(None, description="WeChat App ID")
    app_secret: str | None = Field(None, description="WeChat App Secret")
    default_author: str | None = Field(None, description="Default author name")
    default_thumb_media_id: str | None = Field(None, description="Default cover image media_id")
    need_open_comment: bool | None = Field(None, description="Enable comments")
    only_fans_can_comment: bool | None = Field(None, description="Only fans can comment")
    is_enabled: bool | None = Field(None, description="Enable WeChat publishing")


class WeChatConfigSummary(BaseModel):
    """Schema for WeChat config summary (sensitive data masked)."""
    account_id: str
    app_id_masked: str = Field(..., description="Masked App ID")
    has_app_secret: bool = Field(..., description="Whether app_secret is set")
    default_author: str | None
    is_enabled: bool
    test_status: str | None
    test_message: str | None
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WeChatConfigDetail(WeChatConfigSummary):
    """Schema for full WeChat config detail."""
    need_open_comment: bool
    only_fans_can_comment: bool


class WeChatConfigResponse(BaseModel):
    """Response schema for WeChat config."""
    code: int = 0
    message: str = "ok"
    data: WeChatConfigSummary | None = None


# =============================================================================
# WeChat Test Connection
# =============================================================================


class WeChatTestConnectionRequest(BaseModel):
    """Schema for testing WeChat connection."""
    app_id: str = Field(..., description="WeChat App ID")
    app_secret: str = Field(..., description="WeChat App Secret")


class WeChatTestConnectionResponse(BaseModel):
    """Response schema for connection test."""
    success: bool
    message: str


# =============================================================================
# WeChat Publish Record Schemas
# =============================================================================


class WeChatPublishRecordSummary(BaseModel):
    """Schema for publish record summary."""
    id: int
    draft_id: int
    account_id: str
    wechat_draft_id: str | None
    media_id: str | None
    publish_id: str | None
    publish_status: str
    error_code: str | None
    error_message: str | None
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WeChatPublishStatusResponse(BaseModel):
    """Response schema for publish status query."""
    publish_status: str = Field(..., description="pending, success, failed")
    article_id: str | None = Field(None, description="WeChat article ID")
    msg_id: str | None = Field(None, description="WeChat message ID")
    url: str | None = Field(None, description="Published article URL")


# =============================================================================
# Publish Result
# =============================================================================


class PublishResult(BaseModel):
    """Result of publishing operation."""
    success: bool
    draft_id: int
    wechat_draft_id: str | None = None
    media_id: str | None = None
    publish_id: str | None = None
    publish_status: str = "pending"
    error_code: str | None = None
    error_message: str | None = None
    published_at: datetime | None = None
