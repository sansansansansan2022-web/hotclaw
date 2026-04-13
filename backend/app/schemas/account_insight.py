"""Schemas for account insights and analysis snapshots."""

from datetime import datetime

from pydantic import BaseModel, Field


class ContentLaneResponse(BaseModel):
    lane_id: str
    label: str
    reason: str
    priority: str = "secondary"


class ReferenceOverviewItemResponse(BaseModel):
    id: str
    name: str
    source_type: str
    sync_status: str | None = None
    article_count: int = 0
    notes: str | None = None
    resolved_title: str | None = None
    preview: str | None = None


class RecentTopicItemResponse(BaseModel):
    title: str
    source: str
    status: str | None = None
    created_at: str | None = None


class InsightRiskAlertResponse(BaseModel):
    type: str
    level: str
    title: str
    message: str


class InsightProfileResponse(BaseModel):
    positioning_summary: str
    audience_summary: str | None = None
    tone_summary: str | None = None
    style_keywords: list[str] = Field(default_factory=list)
    banned_angles: list[str] = Field(default_factory=list)


class InsightContentStrategyResponse(BaseModel):
    content_lanes: list[ContentLaneResponse] = Field(default_factory=list)
    recent_topics: list[RecentTopicItemResponse] = Field(default_factory=list)


class InsightReferenceBundleResponse(BaseModel):
    total: int = 0
    items: list[ReferenceOverviewItemResponse] = Field(default_factory=list)


class InsightOperationsResponse(BaseModel):
    status: str
    effective_mode: str | None = None
    requested_mode: str | None = None
    allow_auto_publish: bool | None = None
    preferred_content_lane: str | None = None
    pending_review_count: int | None = None
    recent_failed_publish_count: int | None = None
    recent_failed_task_count: int | None = None
    ops_notes: list[str] = Field(default_factory=list)
    risk_alerts: list[InsightRiskAlertResponse] = Field(default_factory=list)


class AccountInsightSnapshotResponse(BaseModel):
    id: str
    account_id: str
    status: str
    profile: InsightProfileResponse
    content_strategy: InsightContentStrategyResponse
    references: InsightReferenceBundleResponse
    operations: InsightOperationsResponse
    generated_at: datetime
    created_at: datetime
    updated_at: datetime
