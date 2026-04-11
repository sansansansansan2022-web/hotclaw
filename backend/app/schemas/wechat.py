"""WeChat related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeChatConfigBase(BaseModel):
    """Shared fields for account-bound WeChat configuration."""

    app_id: str = Field(..., min_length=4, description="WeChat Official Account App ID")
    app_secret: str = Field(..., min_length=4, description="WeChat Official Account App Secret")
    default_author: str | None = Field(None, description="Default author name used when publishing")
    default_thumb_media_id: str | None = Field(None, description="Pre-uploaded WeChat thumb media_id")
    need_open_comment: bool = Field(True, description="Whether comments are enabled after publish")
    only_fans_can_comment: bool = Field(False, description="Whether only followers can comment")
    is_enabled: bool = Field(True, description="Whether this account can publish to WeChat")


class WeChatConfigCreate(WeChatConfigBase):
    """Payload for creating account-bound WeChat config."""

    account_id: str | None = Field(None, description="Legacy compatibility field; path parameter is preferred")


class WeChatConfigUpdate(BaseModel):
    """Payload for updating account-bound WeChat config."""

    app_id: str | None = Field(None, min_length=4)
    app_secret: str | None = Field(None, min_length=4)
    default_author: str | None = None
    default_thumb_media_id: str | None = None
    need_open_comment: bool | None = None
    only_fans_can_comment: bool | None = None
    is_enabled: bool | None = None


class WeChatConfigRead(BaseModel):
    """Masked WeChat config returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    account_id: str
    app_id_masked: str
    has_app_secret: bool
    app_secret_masked: str | None = None
    default_author: str | None = None
    default_thumb_media_id: str | None = None
    need_open_comment: bool
    only_fans_can_comment: bool
    is_enabled: bool
    access_token_cached: bool = False
    token_expires_at: datetime | None = None
    verified_at: datetime | None = None
    last_test_status: str | None = None
    last_test_error: str | None = None
    created_at: datetime
    updated_at: datetime


# Backward-compatible aliases used by existing frontend code.
WeChatConfigSummary = WeChatConfigRead
WeChatConfigDetail = WeChatConfigRead


class WeChatConnectionTestResponse(BaseModel):
    """Result of testing WeChat connectivity for one account config."""

    success: bool
    message: str
    tested_at: datetime
    token_expires_at: datetime | None = None


class WeChatTestConnectionRequest(BaseModel):
    """Legacy route payload for direct credential testing without persistence."""

    app_id: str = Field(..., min_length=4)
    app_secret: str = Field(..., min_length=4)


class WeChatTestConnectionResponse(BaseModel):
    """Backward-compatible alias for existing frontend API typing."""

    success: bool
    message: str


class PublishToWeChatRequest(BaseModel):
    """Request body for a publish trigger."""

    operator: str = Field("system", description="Human or system operator triggering publish")
    trigger_type: str | None = Field(
        None,
        description="manual_confirm, semi_auto_confirm, full_auto, manual_retry, auto_retry",
    )


class PublishRecordRead(BaseModel):
    """Serialized publish record returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    draft_id: int
    account_id: str
    task_id: str | None = None
    wechat_draft_media_id: str | None = None
    wechat_publish_id: str | None = None
    wechat_article_url: str | None = None
    wechat_msg_data_id: str | None = None
    publish_status: str
    source_mode: str
    trigger_type: str
    attempt_count: int
    retry_count: int
    simulated: bool = False
    simulation_source: str | None = None
    provider: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    published_at: datetime | None = None
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PublishRecordStatusSyncResponse(BaseModel):
    """Result returned after a manual status sync with WeChat."""

    record_id: int
    previous_status: str
    new_status: str
    synced_draft: bool
    message: str


class PublishResult(BaseModel):
    """Result of the publish orchestration pipeline."""

    success: bool
    draft_id: int
    publish_record_id: int | None = None
    wechat_draft_media_id: str | None = None
    wechat_publish_id: str | None = None
    wechat_article_url: str | None = None
    publish_status: str = "pending"
    error_code: str | None = None
    error_message: str | None = None
    decision: dict | None = None
    published_at: datetime | None = None
    simulated: bool = False
    simulation_source: str | None = None
    provider: str | None = None
