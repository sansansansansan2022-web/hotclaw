"""Schemas for account onboarding flows."""

from typing import Literal

from pydantic import BaseModel, Field


class ExistingAccountAnalysisRequest(BaseModel):
    """Request payload for analyzing an existing account from historical content."""

    account_name: str = Field(..., min_length=1, max_length=100)
    content_platform: str = Field(default="wechat", description="wechat / xiaohongshu")
    article_urls: list[str] | None = Field(default=None, description="Best-effort historical article URLs")
    article_texts: list[str] | None = Field(default=None, description="Pasted historical article bodies")


class ExistingAccountAnalysisResponse(BaseModel):
    """Structured onboarding analysis for an existing account."""

    account_name: str
    content_platform: str = "wechat"
    inferred_positioning: str
    inferred_audience: str
    inferred_tone_style: str
    inferred_content_strategy: str
    inferred_reference_accounts_summary: str | None = None
    recommended_operation_mode: str = "semi_auto"
    onboarding_notes: list[str] = Field(default_factory=list)
    extracted_topics: list[str] = Field(default_factory=list)
    style_summary: str
    analysis_confidence: Literal["low", "medium", "high"] = "medium"
    source_summary: str = ""
    used_article_count: int = 0
