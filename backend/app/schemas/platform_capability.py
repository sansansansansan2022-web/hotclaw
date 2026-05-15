"""Schemas for platform capability plugins."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PlatformCapabilityCreateRequest(BaseModel):
    capability_id: str | None = Field(default=None, max_length=128)
    content_platform: str = Field(default="wechat")
    capability_type: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    is_enabled: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)
    prompt_overrides_json: dict[str, Any] = Field(default_factory=dict)


class PlatformCapabilityUpdateRequest(BaseModel):
    content_platform: str | None = None
    capability_type: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    is_enabled: bool | None = None
    status: str | None = None
    config_json: dict[str, Any] | None = None
    prompt_overrides_json: dict[str, Any] | None = None


class PlatformCapabilityResponse(BaseModel):
    capability_id: str
    content_platform: str
    capability_type: str
    name: str
    description: str | None = None
    is_builtin: bool = False
    is_enabled: bool = True
    status: str = "active"
    config_json: dict[str, Any] = Field(default_factory=dict)
    prompt_overrides_json: dict[str, Any] = Field(default_factory=dict)
    source: str = "custom"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlatformCapabilityListResponse(BaseModel):
    capabilities: list[PlatformCapabilityResponse] = Field(default_factory=list)
    total: int = 0
    enabled_count: int = 0
    builtin_count: int = 0


class EffectivePlatformCapabilityResponse(BaseModel):
    content_platform: str
    capabilities: list[PlatformCapabilityResponse] = Field(default_factory=list)
    by_type: dict[str, list[PlatformCapabilityResponse]] = Field(default_factory=dict)
    prompt_hints: dict[str, list[str]] = Field(default_factory=dict)
