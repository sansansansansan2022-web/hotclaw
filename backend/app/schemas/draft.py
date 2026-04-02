"""Draft-related request and response schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class DraftStatus(str):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISCARDED = "discarded"


class PublishStatus(str):
    NOT_PUBLISHED = "not_published"
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class SourceType(str):
    MANUAL_TASK = "manual_task"
    SEMI_AUTO_TASK = "semi_auto_task"


# =============================================================================
# Response
# =============================================================================


class DraftSummary(BaseModel):
    """Draft list item (lighter than detail)."""
    id: int
    task_id: str
    account_id: str | None
    title: str
    selected_topic: str | None
    draft_status: str
    publish_status: str
    publish_review_required: bool
    source_type: str
    word_count: int
    created_at: datetime
    updated_at: datetime


class AuditResultInfo(BaseModel):
    """Brief audit result info for draft detail."""
    passed: bool
    risk_level: str
    overall_comment: str | None
    issues: list | None


class DraftDetail(BaseModel):
    """Full draft detail."""
    id: int
    task_id: str
    account_id: str | None
    account_name: str | None
    title: str
    title_candidates: list | None
    selected_topic: str | None
    summary: str | None
    content_markdown: str
    content_html: str | None
    word_count: int
    tags: list | None
    draft_status: str
    publish_status: str
    publish_review_required: bool
    source_type: str
    confirmed_at: datetime | None
    confirmed_by: str | None
    published_at: datetime | None
    publish_error_message: str | None
    audit_result: AuditResultInfo | None
    created_at: datetime
    updated_at: datetime


class DraftListResponse(BaseModel):
    """Paginated draft list."""
    drafts: list[DraftSummary]
    pagination: dict


class DraftConfirmData(BaseModel):
    """Response after confirming draft publish."""
    draft_id: int
    draft_status: str
    publish_status: str
    confirmed_at: datetime


class DraftDiscardData(BaseModel):
    """Response after discarding draft."""
    draft_id: int
    draft_status: str


class DraftRejectData(BaseModel):
    """Response after rejecting draft."""
    draft_id: int
    draft_status: str


class DraftRerunData(BaseModel):
    """Response after rerunning draft."""
    draft_id: int
    original_task_id: str
    new_task_id: str
    status: str


class DraftCreateData(BaseModel):
    """Response after creating draft from task."""
    draft_id: int
    task_id: str
    account_id: str | None
    draft_status: str
    publish_status: str
