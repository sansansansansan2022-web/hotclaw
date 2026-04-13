"""
Skill 技能配置和调试执行 API 路由

【Skill 技能管理接口】
提供技能列表查询、配置更新和技能调试执行功能。

联动模块：
- Service: app.skills.registry (Skill 注册表)
- Schema: app.schemas.skill (请求/响应序列化)
- Model: app.models.tables.SkillModel (数据库持久化)
- Runtime: app.skills.services.skill_runtime_service (技能运行时)

API 端点：
- GET    /api/v1/skills              Skill 列表查询
- PUT    /api/v1/skills/{id}/config  更新 Skill 配置
- POST   /api/v1/skills/scholar/search  学术论文搜索调试
- POST   /api/v1/skills/github/curate  GitHub 项目整理调试

调用方：
- 前端: frontend/app/settings/skills/* (技能设置页)
- 前端: frontend/app/settings/llm-providers/* (LLM 提供商配置页)
"""

from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.skill import (
    GitHubSkillDebugRequest,
    ScholarSkillDebugRequest,
    SkillConfigUpdateRequest,
)
from app.skills.registry import skill_registry
from app.models.tables import SkillModel
from app.skills.services.skill_runtime_service import skill_runtime_service

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get("")
async def list_skills(db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """
    【Skill 列表查询】

    返回所有已注册的 Skill 技能列表。
    包括技能名称、描述、版本和默认配置。

    返回数据结构：
    - skill_id: Skill 唯一标识符
    - name: Skill 显示名称
    - description: Skill 功能描述
    - config_data: 默认配置数据

    调用方：
    - 前端: frontend/app/settings/skills/page.tsx (技能列表)
    """
    skills = skill_registry.list_all()
    data = []
    for s in skills:
        data.append({
            "skill_id": s.skill_id,
            "name": s.name,
            "description": s.description,
            "version": "1.0.0",
            "config_data": s.config,
            "status": "active",
        })
    return ApiResponse(data={"skills": data})


@router.put("/{skill_id}/config")
async def update_skill_config(
    skill_id: str,
    req: SkillConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    【更新 Skill 配置】

    更新指定 Skill 的配置项（如 API 密钥、参数等）。

    注意：
    - 如果数据库中不存在配置记录，会自动创建
    - config_data 包含技能的各类配置参数

    异常：
    - SkillNotFoundError: Skill 不存在于注册表中
    """
    skill_registry.get(skill_id)

    stmt = select(SkillModel).where(SkillModel.skill_id == skill_id)
    result = await db.execute(stmt)
    db_skill = result.scalar_one_or_none()

    if db_skill is None:
        db_skill = SkillModel(
            skill_id=skill_id,
            name=skill_registry.get(skill_id).name,
            module_path=f"app.skills.{skill_id}",
        )

    if req.config_data is not None:
        db_skill.config_data = req.config_data

    db.add(db_skill)
    await db.flush()

    return ApiResponse(data={"skill_id": skill_id, "updated": True})


@router.post("/scholar/search")
async def debug_scholar_search(
    req: ScholarSkillDebugRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    【学术论文搜索调试接口】

    调用 scholar_paper_search_skill 执行学术论文搜索。
    用于测试和调试技能功能。

    请求参数：
    - task_id: 任务 ID（可选，用于追踪）
    - workspace_id: 工作空间 ID（可选）
    - account_id: 关联账号 ID（可选）
    - query: 搜索关键词
    - max_results: 最大结果数量

    调用方：
    - 前端: 技能调试面板 / 开发者工具

    返回：技能执行结果
    """
    task_id = (req.task_id or f"debug_scholar_{uuid4().hex[:12]}").strip()
    workspace_id = (req.workspace_id or task_id).strip()
    result = await skill_runtime_service.invoke(
        skill_name="scholar_paper_search_skill",
        input_data=req.model_dump(exclude={"task_id", "workspace_id", "account_id"}),
        db=db,
        task_id=task_id,
        workspace_id=workspace_id,
        account_id=req.account_id,
    )
    await db.commit()
    return ApiResponse(data=result)


@router.post("/github/curate")
async def debug_github_curate(
    req: GitHubSkillDebugRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    【GitHub 项目整理调试接口】

    调用 github_project_curator_skill 执行 GitHub 项目整理。
    用于测试和调试技能功能。

    请求参数：
    - task_id: 任务 ID（可选，用于追踪）
    - workspace_id: 工作空间 ID（可选）
    - account_id: 关联账号 ID（可选）
    - keywords: 搜索关键词列表
    - language: 编程语言筛选
    - max_results: 最大结果数量

    调用方：
    - 前端: 技能调试面板 / 开发者工具

    返回：技能执行结果（整理后的 GitHub 项目列表）
    """
    task_id = (req.task_id or f"debug_github_{uuid4().hex[:12]}").strip()
    workspace_id = (req.workspace_id or task_id).strip()
    result = await skill_runtime_service.invoke(
        skill_name="github_project_curator_skill",
        input_data=req.model_dump(exclude={"task_id", "workspace_id", "account_id"}),
        db=db,
        task_id=task_id,
        workspace_id=workspace_id,
        account_id=req.account_id,
    )
    await db.commit()
    return ApiResponse(data=result)