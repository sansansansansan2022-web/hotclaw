"""Skill-related schemas."""

from pydantic import BaseModel


class SkillInfo(BaseModel):
    skill_id: str
    name: str
    description: str | None = None
    version: str
    config_data: dict | None = None
    status: str


class SkillListResponse(BaseModel):
    skills: list[SkillInfo]


class SkillConfigUpdateRequest(BaseModel):
    """Request body for updating skill configuration."""
    config_data: dict | None = None
