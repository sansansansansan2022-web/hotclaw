"""Account-related request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.automation_plan import AutomationPlanCreateRequest, AutomationPlanSummary


# =============================================================================
# Enums
# =============================================================================


class OperationMode(str):
    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"


class PostingFrequency(str):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


# =============================================================================
# Request
# =============================================================================


class AccountCreateRequest(BaseModel):
    """Request body for creating a new account workspace."""

    name: str = Field(..., min_length=1, max_length=100, description="Account display name")
    category: str | None = Field(default=None, max_length=50, description="Account category")
    positioning: str = Field(..., min_length=5, max_length=500, description="Positioning summary")
    audience: str | None = Field(default=None, max_length=200, description="Audience summary")
    tone_style: str | None = Field(default=None, max_length=100, description="Tone and style")
    content_strategy: str | None = Field(default=None, description="Content strategy notes")
    reference_accounts: str | None = Field(default=None, description="Reference account notes")
    # Legacy scheduling inputs kept for compatibility while AutomationPlan remains
    # the runtime source of truth.
    posting_frequency: str | None = Field(default=None, description="Legacy cadence mirror")
    posting_time: str | None = Field(default=None, max_length=10, description="Legacy posting time mirror")
    operation_mode: str = Field(
        default="manual",
        description="Compatibility mirror: manual / semi_auto / full_auto",
    )
    auto_run_enabled: bool = Field(
        default=False,
        description="Compatibility mirror for scheduled enablement",
    )
    auto_publish_enabled: bool = Field(
        default=False,
        description="Compatibility mirror for publish strategy",
    )
    is_active: bool = Field(default=True, description="Whether the workspace is active")
    publish_paused: bool = Field(default=False, description="Whether publishing is paused")
    max_posts_per_day: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Compatibility mirror for daily publish cap",
    )
    min_interval_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,
        description="Compatibility mirror for publish interval",
    )
    automation_plan: AutomationPlanCreateRequest | None = None


class AccountUpdateRequest(BaseModel):
    """Request body for updating an account workspace."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=50)
    positioning: str | None = Field(default=None, min_length=5, max_length=500)
    audience: str | None = Field(default=None, max_length=200)
    tone_style: str | None = Field(default=None, max_length=100)
    content_strategy: str | None = None
    reference_accounts: str | None = None
    # Legacy scheduling inputs kept for compatibility while AutomationPlan remains
    # the runtime source of truth.
    posting_frequency: str | None = Field(default=None)
    posting_time: str | None = Field(default=None, max_length=10)
    operation_mode: str | None = None
    auto_run_enabled: bool | None = None
    auto_publish_enabled: bool | None = None
    is_active: bool | None = None
    publish_paused: bool | None = None
    max_posts_per_day: int | None = Field(default=None, ge=1, le=100)
    min_interval_minutes: int | None = Field(default=None, ge=1, le=1440)


class AccountRunRequest(BaseModel):
    """Optional payload for explicit pre-generation decisions."""

    selection_session_id: str | None = None
    preview_payload: dict | None = None
    creation_note: str | None = None


# =============================================================================
# Response
# =============================================================================


class AccountInfo(BaseModel):
    """Lightweight account info embedded in task responses."""

    account_id: str
    name: str
    positioning: str
    operation_mode: str


class AccountSummary(BaseModel):
    """Account list item with compatibility-mirrored scheduling fields."""

    account_id: str
    name: str
    category: str | None
    positioning: str
    # Compatibility mirror fields only. Effective automation semantics should be
    # read from automation_plan_summary on detail responses.
    operation_mode: str
    posting_frequency: str | None
    auto_run_enabled: bool
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_run_status: str | None
    last_error_message: str | None
    created_at: datetime


class AccountTaskSummary(BaseModel):
    """Brief task info shown within account detail."""

    task_id: str
    status: str
    created_at: datetime
    elapsed_seconds: float | None


class AccountDetail(BaseModel):
    """Full account detail with recent tasks and plan-first automation summary."""

    account_id: str
    name: str
    category: str | None
    positioning: str
    audience: str | None
    tone_style: str | None
    # Compatibility mirror fields only. Frontend should prefer
    # automation_plan_summary for effective automation semantics.
    posting_frequency: str | None
    posting_time: str | None
    content_strategy: str | None
    reference_accounts: str | None
    operation_mode: str
    auto_run_enabled: bool
    auto_publish_enabled: bool
    is_active: bool
    publish_paused: bool
    max_posts_per_day: int | None
    min_interval_minutes: int | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_run_status: str | None
    last_error_message: str | None
    last_publish_status: str | None
    last_publish_error_message: str | None
    last_published_at: datetime | None
    reference_source_count: int = 0
    reference_source_enabled_count: int = 0
    reference_source_last_sync_status: str | None = None
    automation_plan_summary: AutomationPlanSummary | None = None
    latest_ops_context: dict | None = None
    latest_effective_mode: str | None = None
    latest_allow_auto_publish: bool | None = None
    latest_ops_degraded: bool = False
    created_at: datetime
    updated_at: datetime
    recent_tasks: list[AccountTaskSummary]


class AccountCreateData(BaseModel):
    """Response after creating an account."""

    account_id: str
    name: str
    is_active: bool
    operation_mode: str


class AccountRunData(BaseModel):
    """Response after triggering an account run."""

    account_id: str
    task_id: str
    status: str
    operation_mode: str
    effective_mode: str | None = None
    selection_session_id: str | None = None


class AccountListResponse(BaseModel):
    """Paginated account list."""

    accounts: list[AccountSummary]
    pagination: dict
