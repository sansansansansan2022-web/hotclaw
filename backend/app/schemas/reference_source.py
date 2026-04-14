"""Schemas for account reference source management."""

from datetime import datetime

from pydantic import BaseModel, Field


class ReferenceSourceCreateRequest(BaseModel):
    """Create a reference source under an account."""

    source_type: str = Field(..., description="wechat_account / article_url / pasted_article")
    name: str | None = Field(default=None, max_length=120)
    source_value: str = Field(..., min_length=1, description="Handle, URL, or pasted article body")
    notes: str | None = Field(default=None)
    is_enabled: bool = Field(default=True)


class ReferenceSourceUpdateRequest(BaseModel):
    """Patch a reference source."""

    name: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None)
    is_enabled: bool | None = Field(default=None)


class ReferenceSourceResponse(BaseModel):
    """Reference source row returned to the frontend."""

    id: int
    account_id: str
    source_type: str
    name: str
    source_value: str
    notes: str | None
    is_enabled: bool
    sync_status: str
    last_synced_at: datetime | None
    article_count: int
    latest_error_message: str | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime


class ReferenceSourceListResponse(BaseModel):
    """Reference source list payload."""

    account_id: str
    sources: list[ReferenceSourceResponse]
    total: int


class SyncReferenceSourceResponse(BaseModel):
    """Response after manually syncing a reference source."""

    source: ReferenceSourceResponse
    message: str


class WechatArticleSearchItemResponse(BaseModel):
    """Normalized WeChat article search result."""

    title: str
    url: str
    intermediate_url: str | None = None
    summary: str | None = None
    published_at: datetime | None = None
    source_name: str | None = None
    url_resolved: bool = False


class WechatArticleSearchResponse(BaseModel):
    """Response for account-scoped WeChat article search."""

    account_id: str
    query: str
    total: int
    articles: list[WechatArticleSearchItemResponse]


class WechatArticleImportRequest(BaseModel):
    """Import one searched WeChat article into account reference sources."""

    title: str = Field(..., min_length=1, max_length=300)
    url: str = Field(..., min_length=1)
    summary: str | None = None
    source_name: str | None = Field(default=None, max_length=200)
    published_at: datetime | None = None
    intermediate_url: str | None = None
    url_resolved: bool = False
    query: str | None = None
    notes: str | None = None
