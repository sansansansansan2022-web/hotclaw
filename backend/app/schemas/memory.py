"""Pydantic schemas for account memory APIs."""

from datetime import datetime

from pydantic import BaseModel, Field


class ArticleMemoryResponse(BaseModel):
    """Single article memory entry returned to the frontend."""

    id: int
    account_id: str
    source_draft_id: int | None = None
    source_task_id: str | None = None
    article_id: str | None = None
    title: str
    summary: str | None = None
    content_excerpt: str | None = None
    tags: list[str] | None = None
    keywords: list[str] | None = None
    metadata: dict | None = Field(default=None, alias="metadata_json")
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}


class ArticleMemoryListResponse(BaseModel):
    """Paginated/searched list of memories for an account."""

    account_id: str
    total: int
    query: str | None = None
    memories: list[ArticleMemoryResponse]


class ArticleMemoryActionResponse(BaseModel):
    """Result of an admin-style action (rebuild / sync)."""

    account_id: str
    status: str
    message: str | None = None
    affected: int = 0


class AccountNoteResponse(BaseModel):
    """Single curated account note (Hermes-style)."""

    id: int
    account_id: str
    content: str
    char_count: int
    source: str
    source_task_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AccountNoteListResponse(BaseModel):
    """Paged list of account notes plus capacity info."""

    account_id: str
    total: int
    used_chars: int
    char_limit: int
    notes: list[AccountNoteResponse]


class AccountNoteCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=400)
    source: str = "manual"


class AccountNoteUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=400)
