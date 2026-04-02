"""Account-related request and response schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


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
    """Request body for creating a new account."""
    name: str = Field(..., min_length=1, max_length=100, description="账号名称")
    category: str | None = Field(default=None, max_length=50, description="账号类别")
    positioning: str = Field(..., min_length=5, max_length=500, description="账号定位描述")
    audience: str | None = Field(default=None, max_length=200, description="目标读者")
    tone_style: str | None = Field(default=None, max_length=100, description="风格调性")
    posting_frequency: str | None = Field(default=None, description="发布频率")
    posting_time: str | None = Field(default=None, max_length=10, description="发布时间，如 08:00")
    content_strategy: str | None = Field(default=None, description="内容策略")
    reference_accounts: str | None = Field(default=None, description="参考公众号")
    operation_mode: str = Field(default="manual", description="运行模式: manual / semi_auto / full_auto")
    auto_run_enabled: bool = Field(default=False, description="是否允许定时运行")
    auto_publish_enabled: bool = Field(default=False, description="是否允许自动发布")
    is_active: bool = Field(default=True, description="是否启用")


class AccountUpdateRequest(BaseModel):
    """Request body for updating an account."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=50)
    positioning: str | None = Field(default=None, min_length=5, max_length=500)
    audience: str | None = Field(default=None, max_length=200)
    tone_style: str | None = Field(default=None, max_length=100)
    posting_frequency: str | None = Field(default=None)
    posting_time: str | None = Field(default=None, max_length=10)
    content_strategy: str | None = None
    reference_accounts: str | None = None
    operation_mode: str | None = None
    auto_run_enabled: bool | None = None
    auto_publish_enabled: bool | None = None
    is_active: bool | None = None


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
    """Account list item (lighter than detail)."""
    account_id: str
    name: str
    category: str | None
    positioning: str
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
    """Full account detail with recent tasks."""
    account_id: str
    name: str
    category: str | None
    positioning: str
    audience: str | None
    tone_style: str | None
    posting_frequency: str | None
    posting_time: str | None
    content_strategy: str | None
    reference_accounts: str | None
    operation_mode: str
    auto_run_enabled: bool
    auto_publish_enabled: bool
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_run_status: str | None
    last_error_message: str | None
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


class AccountListResponse(BaseModel):
    """Paginated account list."""
    accounts: list[AccountSummary]
    pagination: dict
