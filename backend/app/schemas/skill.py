"""Skill-related schemas."""

from pydantic import BaseModel

from app.skills.schemas.github import GitHubProjectCuratorInput
from app.skills.schemas.scholar import ScholarPaperSearchInput


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


class SkillDebugRequest(BaseModel):
    """Shared debug envelope for runtime skill invocation."""

    task_id: str | None = None
    workspace_id: str | None = None
    account_id: str | None = None


class ScholarSkillDebugRequest(SkillDebugRequest, ScholarPaperSearchInput):
    """Debug request for scholar search."""


class GitHubSkillDebugRequest(SkillDebugRequest, GitHubProjectCuratorInput):
    """Debug request for GitHub curation."""
