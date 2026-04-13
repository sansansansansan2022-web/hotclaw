"""Agent configuration API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.agent import AgentConfigUpdateRequest, AgentCreateRequest
from app.agents.registry import agent_registry
from app.models.tables import AgentModel
from app.core.exceptions import AgentNotFoundError

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("")
async def list_agents(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """List all registered agents."""
    agents = agent_registry.list_all()

    # Batch query DB for custom prompts
    agent_ids = [a.agent_id for a in agents]
    stmt = select(AgentModel.agent_id, AgentModel.prompt_template).where(
        AgentModel.agent_id.in_(agent_ids)
    )
    result = await db.execute(stmt)
    custom_prompts = {row[0]: row[1] for row in result.all()}

    data = []
    for a in agents:
        db_prompt = custom_prompts.get(a.agent_id)
        has_custom = bool(db_prompt)
        data.append({
            "agent_id": a.agent_id,
            "name": a.name,
            "description": a.description,
            "version": "1.0.0",
            "required_skills": [],
            "status": "active",
            "has_custom_prompt": has_custom,
        })
    return ApiResponse(data={"agents": data})


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Get a single agent's detail."""
    agent = agent_registry.get(agent_id)  # Raises AgentNotFoundError

    # Try to get persisted config from DB
    stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
    result = await db.execute(stmt)
    db_agent = result.scalar_one_or_none()

    db_prompt = db_agent.prompt_template if db_agent else None
    has_custom = bool(db_prompt)
    effective_prompt = db_prompt if has_custom else agent.default_system_prompt

    return ApiResponse(data={
        "agent_id": agent.agent_id,
        "name": agent.name,
        "description": agent.description,
        "version": "1.0.0",
        "model_config_data": db_agent.model_config_data if db_agent else None,
        "prompt_template": effective_prompt,
        "prompt_source": "custom" if has_custom else "default",
        "default_system_prompt": agent.default_system_prompt,
        "retry_config": db_agent.retry_config if db_agent else None,
        "status": "active",
    })


@router.put("/{agent_id}/config")
async def update_agent_config(
    agent_id: str,
    req: AgentConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Update an agent's configuration."""
    # Verify agent exists in registry
    agent_registry.get(agent_id)

    stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
    result = await db.execute(stmt)
    db_agent = result.scalar_one_or_none()

    if db_agent is None:
        # Create DB record if it doesn't exist yet
        db_agent = AgentModel(
            agent_id=agent_id,
            name=agent_registry.get(agent_id).name,
            module_path=f"app.agents.{agent_id}",
        )

    updated_fields = []
    if req.model_config_data is not None:
        db_agent.model_config_data = req.model_config_data
        updated_fields.append("model_config_data")
    if req.prompt_template is not None:
        # Empty string means "reset to default" -> store None in DB
        db_agent.prompt_template = req.prompt_template if req.prompt_template.strip() else None
        updated_fields.append("prompt_template")
    if req.retry_config is not None:
        db_agent.retry_config = req.retry_config
        updated_fields.append("retry_config")

    db.add(db_agent)
    await db.flush()

    return ApiResponse(data={
        "agent_id": agent_id,
        "updated_fields": updated_fields,
    })


@router.post("")
async def create_agent_config(
    req: AgentCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    Create a custom agent configuration.

    This creates a database record for customizing an agent's settings
    (prompt_template, model_config, retry_config) without modifying the
    base agent definition.
    """
    # Verify agent exists in registry
    try:
        base_agent = agent_registry.get(req.agent_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{req.agent_id}' not found in registry. Available agents: {[a.agent_id for a in agent_registry.list_all()]}"
        )

    # Check if config already exists
    stmt = select(AgentModel).where(AgentModel.agent_id == req.agent_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration for agent '{req.agent_id}' already exists. Use PUT to update."
        )

    # Create new configuration
    db_agent = AgentModel(
        agent_id=req.agent_id,
        name=req.name or base_agent.name,
        description=req.description,
        module_path=f"app.agents.{req.agent_id}",
        model_config_data=req.model_config_data,
        prompt_template=req.prompt_template,
        retry_config=req.retry_config,
    )

    db.add(db_agent)
    await db.flush()

    return ApiResponse(data={
        "agent_id": req.agent_id,
        "name": db_agent.name,
        "description": db_agent.description,
        "prompt_template": db_agent.prompt_template,
        "model_config_data": db_agent.model_config_data,
        "retry_config": db_agent.retry_config,
        "created_at": db_agent.created_at.isoformat() if db_agent.created_at else None,
    })


@router.delete("/{agent_id}/config")
async def delete_agent_config(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    Delete a custom agent configuration.

    This removes the database record but does not delete the base agent
    from the registry. The agent will revert to using its default configuration.
    """
    # Verify agent exists in registry
    agent_registry.get(agent_id)

    stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
    result = await db.execute(stmt)
    db_agent = result.scalar_one_or_none()

    if db_agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No custom configuration found for agent '{agent_id}'"
        )

    await db.delete(db_agent)
    await db.flush()

    return ApiResponse(data={
        "agent_id": agent_id,
        "deleted": True,
    })
