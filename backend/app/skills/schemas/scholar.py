"""Scholar skill schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.skills.schemas.skill_common import EvidenceItemPayload


class ScholarPaperSearchInput(BaseModel):
    topic: str
    year_from: int | None = None
    year_to: int | None = None
    max_results: int = Field(default=10, ge=1, le=20)
    paper_types: list[str] | None = None
    venue_preference: list[str] | None = None
    must_have: list[str] | None = None
    exclude_terms: list[str] | None = None
    language: str | None = None
    mode: str = "high_level"


class PaperCandidate(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    doi: str | None = None
    abstract_or_summary: str | None = None
    citation_count: int = 0
    paper_type: str | None = None
    why_selected: str
    why_relevant: str
    score_breakdown: dict
    risk_flags: list[str] = Field(default_factory=list)


class ScholarPaperSearchOutput(BaseModel):
    query: str
    normalized_queries: list[str]
    results: list[PaperCandidate]
    summary: str
    reading_path: list[dict]
    evidence_items: list[EvidenceItemPayload]
