"""Agent-related schemas."""

from pydantic import BaseModel


class AgentInfo(BaseModel):
    agent_id: str
    name: str
    description: str | None = None
    version: str
    model_config_data: dict | None = None
    required_skills: list[str] | None = None
    status: str
    prompt_template: str | None = None
    prompt_source: str | None = None
    default_system_prompt: str | None = None
    has_custom_prompt: bool = False


class AgentListResponse(BaseModel):
    agents: list[AgentInfo]


class AgentConfigUpdateRequest(BaseModel):
    """Request body for updating agent configuration."""
    model_config_data: dict | None = None
    prompt_template: str | None = None
    retry_config: dict | None = None
