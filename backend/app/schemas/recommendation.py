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
    high_relevance_count: int = 0
    extended_count: int = 0


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


class RecommendationCoverageResponse(BaseModel):
    requested_min_count: int
    high_relevance_count: int
    extended_count: int
    returned_count: int
    shortage_count: int
    meets_requested_min_count: bool
    relaxed_count: int = 0


class RecommendationShortageNoticeResponse(BaseModel):
    status: Literal["ok", "insufficient_high_relevance", "insufficient_total"]
    reason_code: str | None = None
    message: str | None = None
    recommended_action: str | None = None


class RecommendationSourceDiagnosticResponse(BaseModel):
    source_key: str
    label: str
    source_type: str
    status: Literal["success", "empty", "failed", "disabled", "not_applicable", "cached_only"]
    query: str | None = None
    candidate_count: int = 0
    high_relevance_count: int = 0
    extended_count: int = 0
    filtered_out_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    detail: str | None = None


class RecommendationFilterDiagnosticsResponse(BaseModel):
    raw_candidate_count: int = 0
    high_relevance_count: int = 0
    extended_count: int = 0
    filtered_out_count: int = 0
    filtered_low_relevance_count: int = 0
    filtered_low_authority_count: int = 0
    sources_with_candidates: int = 0
    sources_failed_or_disabled: int = 0


class RecommendationListResponse(BaseModel):
    account_id: str
    filters: RecommendationListFiltersResponse
    summary: RecommendationListSummaryResponse
    min_count: int
    high_relevance_items: list[RecommendedContentItemResponse] = Field(default_factory=list)
    extended_items: list[RecommendedContentItemResponse] = Field(default_factory=list)
    total: int
    coverage: RecommendationCoverageResponse
    shortage_notice: RecommendationShortageNoticeResponse
    source_diagnostics: list[RecommendationSourceDiagnosticResponse] = Field(default_factory=list)
    filter_diagnostics: RecommendationFilterDiagnosticsResponse = Field(
        default_factory=RecommendationFilterDiagnosticsResponse
    )
    refreshed_at: datetime | None = None


class RecommendationSelectRequest(BaseModel):
    recommendation_ids: list[str] = Field(default_factory=list)
    action: Literal["use_for_creation", "save_as_reference", "dismiss", "remove_from_creation"]
    selection_session_id: str | None = None


class RecommendationSelectResponse(BaseModel):
    selection_session: ComposeSelectionSessionResponse | None = None
    selected_recommendations: list[SelectedSourceResponse] = Field(default_factory=list)
    selected_reference_sources: list[SelectedReferenceSourceResponse] = Field(default_factory=list)
