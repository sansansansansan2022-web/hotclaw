"""Skill configuration and debug execution API routes."""

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
    """List all registered skills."""
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
    """Update a skill's configuration."""
    skill_registry.get(skill_id)  # Raises SkillNotFoundError

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
