"""Shared schema helpers for runtime skills."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    """Named score buckets used by ranking outputs."""

    relevance: float = 0.0
    authority: float = 0.0
    freshness: float = 0.0
    practical: float = 0.0
    overall: float = 0.0


class EvidenceItemPayload(BaseModel):
    """Normalized evidence payload written to workspace and persistence."""

    source_type: str
    source_id: str | None = None
    title: str
    url: str | None = None
    summary: str = ""
    raw_payload_json: dict | None = None
    normalized_payload_json: dict | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    authority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    freshness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    practical_score: float = Field(default=0.0, ge=0.0, le=1.0)
    selected_reason: str = ""
    risk_flags: list[str] = Field(default_factory=list)
