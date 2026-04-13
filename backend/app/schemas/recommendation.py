"""Schemas for recommended content and recommendation actions."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.compose_preview import (
    ComposeSelectionSessionResponse,
    SelectedReferenceSourceResponse,
    SelectedSourceResponse,
)


class RecommendationSourceResponse(BaseModel):
    source_type: str
    source_name: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None


class RecommendationScoresResponse(BaseModel):
    relevance: float | None = None
    authority: float | None = None
    freshness: float | None = None
    overall: float | None = None


class RecommendationRationaleResponse(BaseModel):
    reason: str | None = None
    evidence_points: list[str] = Field(default_factory=list)


class RecommendationListFiltersResponse(BaseModel):
    source_type: str | None = None
    sort_by: str
    status: str | None = None


class RecommendationListSummaryResponse(BaseModel):
    source_counts: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)


class RecommendedContentItemResponse(BaseModel):
    id: str
    account_id: str
    title: str
    summary: str | None = None
    source: RecommendationSourceResponse
    scores: RecommendationScoresResponse
    rationale: RecommendationRationaleResponse
    topic_tags: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class RecommendationListResponse(BaseModel):
    account_id: str
    filters: RecommendationListFiltersResponse
    summary: RecommendationListSummaryResponse
    recommendations: list[RecommendedContentItemResponse]
    total: int
    refreshed_at: datetime | None = None


class RecommendationSelectRequest(BaseModel):
    recommendation_ids: list[str] = Field(default_factory=list)
    action: Literal["use_for_creation", "save_as_reference", "dismiss"]
    selection_session_id: str | None = None


class RecommendationSelectResponse(BaseModel):
    selection_session: ComposeSelectionSessionResponse | None = None
    selected_recommendations: list[SelectedSourceResponse] = Field(default_factory=list)
    selected_reference_sources: list[SelectedReferenceSourceResponse] = Field(default_factory=list)
