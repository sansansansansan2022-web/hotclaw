"""
Agent 配置 API 路由

【Agent 智能体配置管理接口】
提供 Agent 智能体的注册、查询、配置更新和自定义提示词管理功能。

联动模块：
- Service: app.agents.registry (Agent 注册表)
- Schema: app.schemas.agent (请求/响应序列化)
- Model: app.models.tables.AgentModel (数据库持久化)
- Exception: app.core.exceptions.AgentNotFoundError

API 端点：
- GET    /api/v1/agents              Agent 列表查询
- GET    /api/v1/agents/{id}         Agent 详情查询
- POST   /api/v1/agents              创建 Agent 自定义配置
- PUT    /api/v1/agents/{id}/config  更新 Agent 配置
- DELETE /api/v1/agents/{id}/config  删除 Agent 自定义配置

调用方：
- 前端: frontend/app/settings/agents/* (智能体设置页)
- 前端 API: frontend/lib/api.ts (listAgents, getAgent, updateAgentConfig 等)
"""

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
    """
    【Agent 列表查询】

    返回所有已注册的 Agent 智能体列表。
    从 Agent 注册表获取基础信息，同时查询数据库中的自定义配置。

    返回数据结构：
    - agent_id: Agent 唯一标识符
    - name: Agent 显示名称
    - description: Agent 功能描述
    - has_custom_prompt: 是否存在自定义提示词

    调用方：
    - 前端: frontend/app/settings/agents/page.tsx (智能体列表)
    """
    agents = agent_registry.list_all()

    # 批量查询数据库中的自定义提示词
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
    """
    【Agent 详情查询】

    获取单个 Agent 的完整配置信息，包括：
    - 基础信息（名称、描述、版本）
    - 模型配置（model_config_data）
    - 提示词配置（prompt_template）
    - 重试配置（retry_config）

    提示词优先级：数据库自定义 > 默认提示词

    调用方：
    - 前端: frontend/app/settings/agents/[id]/page.tsx (Agent 详情编辑页)

    异常：
    - 404: Agent 不存在于注册表中
    """
    agent = agent_registry.get(agent_id)

    # 尝试从数据库获取持久化的配置
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
    """
    【更新 Agent 配置】

    更新指定 Agent 的配置项：
    - model_config_data: 模型配置（如 temperature、max_tokens 等）
    - prompt_template: 自定义提示词模板
    - retry_config: 重试策略配置

    注意：
    - 如果数据库中不存在配置记录，会自动创建
    - prompt_template 为空字符串时，表示重置为默认提示词

    调用方：
    - 前端: frontend/app/settings/agents/[id]/page.tsx (保存配置)

    异常：
    - 404: Agent 不存在于注册表中
    """
    # 验证 Agent 是否存在于注册表中
    agent_registry.get(agent_id)

    stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
    result = await db.execute(stmt)
    db_agent = result.scalar_one_or_none()

    if db_agent is None:
        # 如果数据库中不存在配置记录，创建新记录
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
        # 空字符串表示"重置为默认" -> 在数据库中存储 None
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
    【创建 Agent 自定义配置】

    为已注册的 Agent 创建数据库配置记录，用于存储：
    - 自定义提示词（prompt_template）
    - 模型配置（model_config_data）
    - 重试配置（retry_config）

    注意：
    - 只会创建数据库配置记录，不会修改注册表中的基础 Agent 定义
    - 如果配置已存在，返回 409 冲突错误

    调用方：
    - 前端: frontend/app/settings/agents/[id]/page.tsx (新建配置)

    异常：
    - 404: Agent 不存在于注册表中
    - 409: 配置已存在（需要使用 PUT 更新）
    """
    # 验证 Agent 是否存在于注册表中
    try:
        base_agent = agent_registry.get(req.agent_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{req.agent_id}' not found in registry. Available agents: {[a.agent_id for a in agent_registry.list_all()]}"
        )

    # 检查配置是否已存在
    stmt = select(AgentModel).where(AgentModel.agent_id == req.agent_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration for agent '{req.agent_id}' already exists. Use PUT to update."
        )

    # 创建新的配置记录
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
    【删除 Agent 自定义配置】

    删除数据库中的 Agent 配置记录。
    删除后 Agent 将使用注册表中的默认配置。

    注意：
    - 只会删除数据库配置记录，不会删除注册表中的基础 Agent 定义
    - 不会影响正在运行的任务

    调用方：
    - 前端: frontend/app/settings/agents/[id]/page.tsx (删除配置)

    异常：
    - 404: Agent 不存在于注册表中，或没有自定义配置
    """
    # 验证 Agent 是否存在于注册表中
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