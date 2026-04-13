"""GitHub skill schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.skills.schemas.skill_common import EvidenceItemPayload


class GitHubProjectCuratorInput(BaseModel):
    topic: str
    time_window: str | None = None
    language_filters: list[str] | None = None
    max_results: int = Field(default=10, ge=1, le=20)
    exclude_terms: list[str] | None = None
    categories: list[str] | None = None
    require_license: bool = False
    prefer_active: bool = True
    mode: str = "curated"


class RepoCandidate(BaseModel):
    full_name: str
    repo_name: str
    owner: str
    url: str
    description: str | None = None
    primary_language: str | None = None
    stars: int = 0
    forks: int = 0
    updated_at: str | None = None
    pushed_at: str | None = None
    license: str | None = None
    topics: list[str] = Field(default_factory=list)
    category: str
    why_selected: str
    best_for: str
    score_breakdown: dict
    risk_flags: list[str] = Field(default_factory=list)


class GitHubProjectCuratorOutput(BaseModel):
    query: str
    normalized_queries: list[str]
    results: list[RepoCandidate]
    summary: str
    buckets: dict[str, list[dict]]
    evidence_items: list[EvidenceItemPayload]
