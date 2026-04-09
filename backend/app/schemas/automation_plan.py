"""Schemas for account automation plan management."""

from datetime import datetime

from pydantic import BaseModel, Field


class AutomationPlanCreateRequest(BaseModel):
    """Create or seed an automation plan for an account."""

    plan_type: str = Field(default="manual", description="manual / semi_auto / full_auto")
    is_enabled: bool = Field(default=False)
    run_strategy: str = Field(default="manual_only", description="manual_only / scheduled / hybrid")
    schedule_type: str = Field(default="none", description="none / daily / weekly / monthly")
    schedule_config: dict | None = Field(default=None)
    auto_publish_enabled: bool = Field(default=False)
    publish_review_required: bool = Field(default=True)
    max_posts_per_day: int | None = Field(default=None, ge=1, le=100)
    min_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    notes: str | None = Field(default=None)


class AutomationPlanUpdateRequest(BaseModel):
    """Patch the active automation plan for an account."""

    plan_type: str | None = Field(default=None)
    is_enabled: bool | None = Field(default=None)
    run_strategy: str | None = Field(default=None)
    schedule_type: str | None = Field(default=None)
    schedule_config: dict | None = Field(default=None)
    auto_publish_enabled: bool | None = Field(default=None)
    publish_review_required: bool | None = Field(default=None)
    max_posts_per_day: int | None = Field(default=None, ge=1, le=100)
    min_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    timezone: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None)


class AutomationPlanSummary(BaseModel):
    """Effective automation plan summary returned to the frontend."""

    id: int | None = None
    account_id: str
    config_source: str = Field(default="plan", description="plan / legacy_fallback")
    plan_type: str
    is_enabled: bool
    run_strategy: str
    schedule_type: str
    schedule_config: dict | None = None
    schedule_summary: str | None = None
    auto_publish_enabled: bool
    publish_review_required: bool
    max_posts_per_day: int | None = None
    min_interval_minutes: int | None = None
    timezone: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    notes: str | None = None
    latest_status: str | None = None
    is_active_plan: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AutomationPlanResponse(AutomationPlanSummary):
    """Stored automation plan row response."""
