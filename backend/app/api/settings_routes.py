"""Settings route aliases for frontend settings pages."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import agent_registry
from app.db.session import get_db
from app.models.tables import AgentModel, LLMProviderModel
from app.schemas.agent import AgentInfo
from app.schemas.skill import SkillInfo
from app.skills.registry import skill_registry
from app.api.llm_provider_routes import LLMProviderResponse
from app.services.system_config_service import SystemConfigService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("/agents")
async def list_settings_agents(db: AsyncSession = Depends(get_db)) -> dict[str, list[AgentInfo]]:
    """List agents for settings pages."""
    agents = agent_registry.list_all()
    agent_ids = [agent.agent_id for agent in agents]

    custom_prompts: dict[str, str | None] = {}
    if agent_ids:
        result = await db.execute(
            select(AgentModel.agent_id, AgentModel.prompt_template).where(AgentModel.agent_id.in_(agent_ids))
        )
        custom_prompts = {row[0]: row[1] for row in result.all()}

    payload: list[AgentInfo] = []
    for agent in agents:
        prompt_value = custom_prompts.get(agent.agent_id)
        payload.append(
            AgentInfo(
                agent_id=agent.agent_id,
                name=agent.name,
                description=agent.description,
                version="1.0.0",
                required_skills=[],
                status="active",
                has_custom_prompt=bool(prompt_value),
            )
        )

    return {"agents": payload}


@router.get("/skills")
async def list_settings_skills() -> dict[str, list[SkillInfo]]:
    """List skills for settings pages."""
    skills = skill_registry.list_all()
    payload = [
        SkillInfo(
            skill_id=skill.skill_id,
            name=skill.name,
            description=skill.description,
            version="1.0.0",
            config_data=skill.config,
            status="active",
        )
        for skill in skills
    ]
    return {"skills": payload}


@router.get("/providers", response_model=list[LLMProviderResponse])
async def list_settings_providers(db: AsyncSession = Depends(get_db)) -> list[LLMProviderResponse]:
    """List providers for settings pages."""
    result = await db.execute(select(LLMProviderModel).order_by(LLMProviderModel.is_default.desc()))
    return list(result.scalars().all())


@router.get("/system-configs/all", response_model=dict[str, Any])
async def get_settings_system_configs(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return flattened system config key/value map for settings pages."""
    return await SystemConfigService(db).to_dict(mask_sensitive=False)
