"""
Task API routes.

【任务 API 路由】
处理任务相关的 HTTP 请求，包括创建、查询、列表。

设计原则（来自 NOTICE.md）：
- api/ 层只处理请求/响应，不包含核心业务逻辑
- 核心逻辑委托给 services/ 层

面试点：
- FastAPI Depends 依赖注入
- asyncio.create_task 后台任务
- 分页查询
- API 响应格式设计
"""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.logger import get_logger
from app.models.tables import ArticleDraftModel
from app.schemas.common import ApiResponse
from app.schemas.task import (
    TaskArtifactListResponse,
    TaskArtifactResponse,
    TaskCreateRequest,
    TaskEffectiveInputResponse,
)
from app.orchestrator.engine import orchestrator_engine
from app.services.task_service import task_service
from app.services.task_artifact_service import task_artifact_service
from app.services.account_harness_service import account_harness_service
from app.services.account_run_dispatch_service import account_run_dispatch_service
from app.skills.services.evidence_service import evidence_service
from app.skills.services.skill_runtime_service import skill_runtime_service
from app.core.tracer import get_trace_id, generate_trace_id, set_trace_id, set_task_id

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])
logger = get_logger(__name__)

# Store background tasks for cleanup
# 【后台任务追踪】
# 存储 asyncio.Task 引用，防止被垃圾回收
_background_tasks: dict[str, asyncio.Task] = {}


def _ensure_utc(dt: datetime | None) -> datetime | None:
    """Treat naive timestamps loaded from SQLite as UTC for API reads."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _isoformat_utc(dt: datetime | None) -> str | None:
    normalized = _ensure_utc(dt)
    return normalized.isoformat() if normalized else None


async def _run_task_in_background(tid: str) -> None:
    """
    在独立数据库会话中运行任务（后台执行）。

    【关键】为什么需要独立会话？
    FastAPI 请求的 db 会话会在请求结束后关闭，
    但任务执行可能持续几分钟，不能依赖请求会话。
    所以创建独立的 session。

    工作流程：
    1. 创建独立数据库会话
    2. 设置 trace_id
    3. 调用 task_service.run_task() 执行编排引擎
    4. 捕获所有异常，打印堆栈（防止静默失败）
    5. 完成后从 _background_tasks 移除引用
    """
    from app.db.session import async_session_factory
    from app.services.task_service import task_service
    from app.core.tracer import set_task_id

    async with async_session_factory() as bg_db:
        try:
            trace_id = get_trace_id() or generate_trace_id()
            set_trace_id(trace_id)
            set_task_id(tid)
            await task_service.run_task(tid, bg_db)
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            _background_tasks.pop(tid, None)


@router.post("")
async def create_task(
    req: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    Create a new content generation task.

    【创建任务 API】

    工作流程：
    1. 验证输入（positioning 非空，长度符合要求）
    2. 创建 TaskModel 记录
    3. 提交到数据库
    4. 异步启动编排引擎（不阻塞 HTTP 响应）

    Returns:
        { task_id, status, created_at, workflow_id }

    注意：
    - 使用 asyncio.create_task 启动后台任务，立即返回响应
    - 客户端通过 SSE 流监听任务进度
    """
    task = await task_service.create_task(
        positioning=req.positioning,
        workflow_id=req.workflow_id,
        db=db,
    )
    await db.commit()

    # 提取可序列化字段（ORM 对象不能直接 JSON 序列化）
    task_id = task.id
    task_status = task.status
    task_workflow_id = task.workflow_id
    created_at = task.created_at.isoformat() if task.created_at else None

    # 【异步执行】启动后台任务，立即返回响应
    # 这样用户立即收到 task_id，可以开始 SSE 订阅
    bg_task = asyncio.create_task(_run_task_in_background(task_id))
    _background_tasks[task_id] = bg_task

    return ApiResponse(data={
        "task_id": task_id,
        "status": task_status,
        "created_at": created_at,
        "workflow_id": task_workflow_id,
    })


@router.get("/{task_id}/status")
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """
    Query task status.

    【任务状态查询】
    返回当前执行进度，用于前端轮询或 SSE 补充。

    Returns:
        { task_id, status, current_node, progress: {total_nodes, completed_nodes, current_node_index}, ... }
    """
    task = await task_service.get_task(task_id, db)
    node_runs = await task_service.get_node_runs(task_id, db)

    completed_nodes = sum(1 for n in node_runs if n.status == "completed")
    current_node = None
    current_index = 0
    for i, n in enumerate(node_runs):
        if n.status == "running":
            current_node = n.node_id
            current_index = i + 1
            break

    elapsed = None
    if task.elapsed_seconds is not None:
        elapsed = task.elapsed_seconds
    elif task.started_at:
        started_at = _ensure_utc(task.started_at)
        if started_at is not None:
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()

    return ApiResponse(data={
        "task_id": task.id,
        "status": task.status,
        "current_node": current_node,
        "progress": {
            "total_nodes": max(orchestrator_engine.get_workflow_node_count(), len(node_runs)),
            "completed_nodes": completed_nodes,
            "current_node_index": current_index,
        },
        "started_at": _isoformat_utc(task.started_at),
        "elapsed_seconds": elapsed,
    })


@router.get("/{task_id}")
async def get_task_detail(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """
    Query full task detail including results.

    【任务详情查询】
    返回完整任务信息和最终产出（result_data）。

    Returns:
        { task_id, status, input_data, result_data, timestamps, tokens, ... }
    """
    task = await task_service.get_task(task_id, db)
    account_name = task.account.name if getattr(task, "account", None) else None
    logger.info(
        "task_detail_loaded",
        task_id=task.id,
        account_id=task.account_id,
        account_name=account_name,
    )

    latest_draft = None
    draft_result = await db.execute(
        select(ArticleDraftModel)
        .where(ArticleDraftModel.task_id == task.id)
        .order_by(desc(ArticleDraftModel.updated_at), desc(ArticleDraftModel.id))
        .limit(1)
    )
    draft = draft_result.scalar_one_or_none()
    if draft is not None:
        latest_draft = {
            "id": draft.id,
            "account_id": draft.account_id,
            "title": draft.title,
            "draft_status": draft.draft_status,
            "publish_status": draft.publish_status,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }

    return ApiResponse(data={
        "task_id": task.id,
        "account_id": task.account_id,
        "account_name": account_name,
        "status": task.status,
        "input_data": task.input_data,
        "workflow_id": task.workflow_id,
        "result_data": task.result_data,
        "ops_context": account_harness_service.extract_ops_context(task.input_data, task.result_data),
        "error_message": task.error_message,
        "created_at": _isoformat_utc(task.created_at),
        "started_at": _isoformat_utc(task.started_at),
        "completed_at": _isoformat_utc(task.completed_at),
        "elapsed_seconds": task.elapsed_seconds,
        "total_tokens": task.total_tokens,
        "latest_draft": latest_draft,
    })


@router.get("/{task_id}/nodes")
async def get_task_nodes(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """
    Query all node execution records for a task.

    【节点执行记录查询】
    返回每个智能体的执行详情，包括耗时、token 使用量、输出数据。
    """
    node_runs = await task_service.get_node_runs(task_id, db)

    nodes_data = []
    for n in node_runs:
        runtime = n.output_data.get("_runtime") if isinstance(n.output_data, dict) else None
        nodes_data.append({
            "node_id": n.node_id,
            "agent_id": n.agent_id,
            "name": orchestrator_engine.get_node_display_name(n.node_id, n.agent_id),
            "status": n.status,
            "input_data": n.input_data,
            "output_data": n.output_data,
            "started_at": _isoformat_utc(n.started_at),
            "completed_at": _isoformat_utc(n.completed_at),
            "elapsed_seconds": task_service.calculate_elapsed_seconds(
                status=n.status,
                started_at=n.started_at,
                completed_at=n.completed_at,
                elapsed_seconds=n.elapsed_seconds,
            ),
            "prompt_tokens": n.prompt_tokens,
            "completion_tokens": n.completion_tokens,
            "retry_count": int(runtime.get("retry_count") or 0) if isinstance(runtime, dict) else 0,
            "model_used": n.model_used,
            "runtime": runtime,
            "degraded": n.degraded,
            "error_message": n.error_message,
        })

    return ApiResponse(data={"nodes": nodes_data})


@router.get("/{task_id}/artifacts")
async def get_task_artifacts(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    task = await task_service.get_task(task_id, db)
    artifacts = await task_artifact_service.list_task_artifacts(task_id, db)
    response = TaskArtifactListResponse(
        task_id=task.id,
        account_id=task.account_id,
        status=task.status,
        artifacts=[TaskArtifactResponse(**artifact) for artifact in artifacts],
    )
    return ApiResponse(data=response.model_dump(mode="json"))


@router.get("/{task_id}/artifacts/{artifact_key}")
async def get_task_artifact(task_id: str, artifact_key: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    await task_service.get_task(task_id, db)
    artifact = await task_artifact_service.get_task_artifact(task_id, artifact_key, db)
    response = TaskArtifactResponse(**artifact)
    return ApiResponse(data=response.model_dump(mode="json"))


@router.get("/{task_id}/effective-input")
async def get_task_effective_input(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    effective_input = await task_artifact_service.get_effective_input(task_id, db)
    response = TaskEffectiveInputResponse(**effective_input)
    return ApiResponse(data=response.model_dump(mode="json"))


@router.get("/{task_id}/evidence")
async def get_task_evidence(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    await task_service.get_task(task_id, db)
    rows = await evidence_service.list_task_evidence(db, task_id)
    return ApiResponse(
        data={
            "task_id": task_id,
            "evidence": evidence_service.serialize_rows(rows),
            "count": len(rows),
        }
    )


@router.get("/{task_id}/skill-invocations")
async def get_task_skill_invocations(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """
    【任务技能调用记录查询】

    获取任务执行过程中调用的 Skill 技能记录。
    包括技能名称、输入参数、输出结果、执行时间等信息。

    返回数据结构：
    - task_id: 任务 ID
    - invocations: 技能调用记录列表
    - count: 调用次数

    调用方：
    - 前端: frontend/app/task/[id]/page.tsx (任务详情页 - 技能调用 Tab)
    """
    await task_service.get_task(task_id, db)
    rows = await skill_runtime_service.list_task_invocations(db, task_id)
    return ApiResponse(
        data={
            "task_id": task_id,
            "invocations": skill_runtime_service.serialize_invocations(rows),
            "count": len(rows),
        }
    )


@router.get("")
async def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    List tasks with pagination.

    【任务列表查询】
    支持分页和状态过滤。

    Query 参数：
    - page: 页码（从 1 开始）
    - page_size: 每页数量（最大 100）
    - status: 可选，筛选状态（running/completed/failed）

    Returns:
        { tasks: [...], pagination: { page, page_size, total } }
    """
    tasks, total = await task_service.list_tasks(
        db,
        page=page,
        page_size=page_size,
        status=status,
        account_id=account_id,
    )

    tasks_data = []
    for t in tasks:
        positioning = ""
        if t.input_data and isinstance(t.input_data, dict):
            positioning = t.input_data.get("positioning", "")

        # Extract audit_result from result_data
        audit_result = None
        if t.result_data and isinstance(t.result_data, dict):
            audit_result = t.result_data.get("audit_result")

        tasks_data.append({
            "task_id": t.id,
            "account_id": t.account_id,
            "account_name": t.account.name if getattr(t, "account", None) else None,
            "positioning_summary": positioning[:50] + ("..." if len(positioning) > 50 else ""),
            "status": t.status,
            "created_at": _isoformat_utc(t.created_at),
            "elapsed_seconds": t.elapsed_seconds,
            "error_message": t.error_message,
            "audit_result": audit_result,
        })

    return ApiResponse(data={
        "tasks": tasks_data,
        "pagination": {"page": page, "page_size": page_size, "total": total},
    })


@router.post("/{task_id}/rerun")
async def rerun_task(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """
    Rerun a completed or failed task.

    【重跑任务 API】

    工作流程：
    1. 查询任务状态（不允许 running 状态重跑）
    2. 删除旧的节点运行记录
    3. 重置任务状态为 pending
    4. 清空 result_data 和 error_message
    5. 异步启动编排引擎

    Returns:
        { task_id, status, created_at, workflow_id }
    """
    task = await task_service.rerun_task(task_id, db)
    await db.commit()

    bg_task = asyncio.create_task(_run_task_in_background(task.id))
    _background_tasks[task.id] = bg_task

    return ApiResponse(data={
        "task_id": task.id,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "workflow_id": task.workflow_id,
    })


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """
    Delete a task and its task-scoped artifacts.

    Active tasks are first cancelled/stopped, then drafts, node runs, evidence,
    publish records and task-scoped logs are removed.
    """
    local_task = _background_tasks.pop(task_id, None)
    cancelled_local_worker = False
    if local_task is not None:
        local_task.cancel()
        cancelled_local_worker = True
    cancelled_account_worker = account_run_dispatch_service.cancel(task_id)

    result = await task_service.delete_task(task_id, db)
    await db.commit()
    result["cancelled_worker"] = bool(cancelled_local_worker or cancelled_account_worker)
    return ApiResponse(data=result)
