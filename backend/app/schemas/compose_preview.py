"""Schemas for compose selection and creation preview."""

from datetime import datetime

from pydantic import BaseModel, Field


class ComposeSelectionSessionResponse(BaseModel):
    id: str
    account_id: str
    selected_recommendation_ids: list[str] = Field(default_factory=list)
    selected_reference_source_ids: list[str] = Field(default_factory=list)
    creation_note: str | None = None
    preferred_lane: str | None = None
    title_direction: str | None = None
    source_confirmed: bool = False
    outline_confirmed: bool = False
    preview_version: int = 0
    approved_outline_seed: dict | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ComposeSelectionSessionCreateRequest(BaseModel):
    creation_note: str | None = None
    preferred_lane: str | None = None
    title_direction: str | None = None
    reference_source_ids: list[int] = Field(default_factory=list)


class ComposePreviewRequest(BaseModel):
    selection_session_id: str
    creation_note: str | None = None
    preferred_lane: str | None = None
    title_direction: str | None = None
    preview_payload: dict | None = None


class ComposeSubmitRequest(BaseModel):
    creation_note: str | None = None
    preferred_lane: str | None = None
    title_direction: str | None = None
    preview_payload: dict | None = None


class SelectedSourceResponse(BaseModel):
    id: str
    title: str
    summary: str | None = None
    source_type: str
    source_name: str | None = None
    source_url: str | None = None
    reason: str | None = None
    topic_tags: list[str] = Field(default_factory=list)


class SelectedReferenceSourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    sync_status: str
    notes: str | None = None
    preview: str | None = None


class ComposeProfileSummaryResponse(BaseModel):
    positioning_summary: str
    audience_summary: str | None = None
    tone_summary: str | None = None
    preferred_lane: str | None = None
    style_keywords: list[str] = Field(default_factory=list)
    creation_note: str | None = None


class ComposeSourceBundleResponse(BaseModel):
    selected_source_count: int = 0
    selected_reference_source_count: int = 0
    source_types: list[str] = Field(default_factory=list)


class ComposeLaneResponse(BaseModel):
    id: str
    label: str
    input_hint: str | None = None
    reason: str


class ComposeQueryPlanResponse(BaseModel):
    lane: ComposeLaneResponse
    selected_topic: str | None = None
    selected_title: str | None = None
    primary_queries: list[str] = Field(default_factory=list)
    secondary_queries: list[str] = Field(default_factory=list)
    source_preferences: list[str] = Field(default_factory=list)
    banned_angles: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)


class TopicDirectionResponse(BaseModel):
    title: str
    angle: str
    topic_kind: str
    reason: str
    source_ids: list[str] = Field(default_factory=list)


class TitleDirectionResponse(BaseModel):
    title: str
    style: str
    rationale: str


class OutlineSectionPreviewResponse(BaseModel):
    section_id: str
    heading: str
    purpose: str
    key_points: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class OutlinePreviewResponse(BaseModel):
    article_goal: str
    why_this_topic: str
    strategic_angle: str
    reference_basis: str
    target_reader: str
    content_lane: str
    target_reader_takeaway: str
    opening_hook: str
    emotional_arc: str
    sections: list[OutlineSectionPreviewResponse] = Field(default_factory=list)
    ending_cta: str
    estimated_word_count: int
    summary: str


class CitationGuardrailsResponse(BaseModel):
    must_ground_titles_in_evidence: bool = True
    must_ground_repo_names_in_evidence: bool = True


class ComposePreviewResponse(BaseModel):
    selection_session: ComposeSelectionSessionResponse
    account_profile_summary: ComposeProfileSummaryResponse
    source_bundle: ComposeSourceBundleResponse
    selected_sources: list[SelectedSourceResponse] = Field(default_factory=list)
    selected_reference_sources: list[SelectedReferenceSourceResponse] = Field(default_factory=list)
    query_plan: ComposeQueryPlanResponse
    topic_directions: list[TopicDirectionResponse] = Field(default_factory=list)
    title_directions: list[TitleDirectionResponse] = Field(default_factory=list)
    outline_preview: OutlinePreviewResponse
    citation_guardrails: CitationGuardrailsResponse


class ComposeSelectionSessionBundleResponse(BaseModel):
    selection_session: ComposeSelectionSessionResponse
    selected_recommendations: list[SelectedSourceResponse] = Field(default_factory=list)
    selected_reference_sources: list[SelectedReferenceSourceResponse] = Field(default_factory=list)


class ComposeReferenceSourceSelectionRequest(BaseModel):
    reference_source_ids: list[int] = Field(default_factory=list)


class ComposeSourceConfirmationRequest(BaseModel):
    confirmed: bool = True


class ComposeOutlineConfirmationRequest(BaseModel):
    preview_version: int = Field(..., ge=1)
    approved_outline_seed: dict
