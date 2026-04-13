"""Agent-related schemas."""

from pydantic import BaseModel, Field


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
    retry_config: dict | None = None


class AgentListResponse(BaseModel):
    agents: list[AgentInfo]


class AgentConfigUpdateRequest(BaseModel):
    """Request body for updating agent configuration."""
    model_config_data: dict | None = None
    prompt_template: str | None = None
    retry_config: dict | None = None


class AgentCreateRequest(BaseModel):
    """Request body for creating a custom agent configuration."""
    agent_id: str = Field(..., description="Agent ID (must match a registered agent)")
    name: str = Field(..., description="Custom name for this agent configuration")
    description: str | None = Field(None, description="Description of this agent configuration")
    prompt_template: str | None = Field(None, description="Custom system prompt template")
    model_config_data: dict | None = Field(None, description="Custom model configuration")
    retry_config: dict | None = Field(None, description="Retry configuration")


class AgentCreateResponse(BaseModel):
    """Response after creating an agent configuration."""
    agent_id: str
    name: str
    description: str | None = None
    prompt_template: str | None = None
    model_config_data: dict | None = None
    retry_config: dict | None = None
    created_at: str
