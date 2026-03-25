"""Task API routes.

Per NOTICE.md section 5: api/ only handles request/response, no core business logic.
"""

import asyncio
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, async_session_factory
from app.schemas.common import ApiResponse
from app.schemas.task import TaskCreateRequest
from app.services.task_service import task_service
from app.core.tracer import get_trace_id, set_task_id

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("")
async def create_task(
    req: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Create a new content generation task."""
    task = await task_service.create_task(
        positioning=req.positioning,
        workflow_id=req.workflow_id,
        db=db,
    )
    await db.commit()

    # Run orchestrator in background so the HTTP response returns immediately
    task_id = task.id

    async def _run_in_background(tid: str) -> None:
        async with async_session_factory() as bg_db:
            try:
                set_task_id(tid)
                await task_service.run_task(tid, bg_db)
            except Exception:
                pass  # Errors already handled inside run_task

    background_tasks.add_task(_run_in_background, task_id)

    return ApiResponse(data={
        "task_id": task.id,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "workflow_id": task.workflow_id,
    })


@router.get("/{task_id}/status")
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Query task status."""
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
        from datetime import datetime, timezone
        elapsed = (datetime.now(timezone.utc) - task.started_at).total_seconds()

    return ApiResponse(data={
        "task_id": task.id,
        "status": task.status,
        "current_node": current_node,
        "progress": {
            "total_nodes": 6,
            "completed_nodes": completed_nodes,
            "current_node_index": current_index,
        },
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "elapsed_seconds": elapsed,
    })


@router.get("/{task_id}")
async def get_task_detail(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Query full task detail including results."""
    task = await task_service.get_task(task_id, db)

    return ApiResponse(data={
        "task_id": task.id,
        "status": task.status,
        "input_data": task.input_data,
        "workflow_id": task.workflow_id,
        "result_data": task.result_data,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "elapsed_seconds": task.elapsed_seconds,
        "total_tokens": task.total_tokens,
    })


@router.get("/{task_id}/nodes")
async def get_task_nodes(task_id: str, db: AsyncSession = Depends(get_db)) -> ApiResponse:
    """Query all node execution records for a task."""
    node_runs = await task_service.get_node_runs(task_id, db)

    nodes_data = []
    for n in node_runs:
        nodes_data.append({
            "node_id": n.node_id,
            "agent_id": n.agent_id,
            "status": n.status,
            "input_data": n.input_data,
            "output_data": n.output_data,
            "started_at": n.started_at.isoformat() if n.started_at else None,
            "completed_at": n.completed_at.isoformat() if n.completed_at else None,
            "elapsed_seconds": n.elapsed_seconds,
            "prompt_tokens": n.prompt_tokens,
            "completion_tokens": n.completion_tokens,
            "model_used": n.model_used,
            "degraded": n.degraded,
            "error_message": n.error_message,
        })

    return ApiResponse(data={"nodes": nodes_data})


@router.get("")
async def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List tasks with pagination."""
    tasks, total = await task_service.list_tasks(db, page=page, page_size=page_size, status=status)

    tasks_data = []
    for t in tasks:
        positioning = ""
        if t.input_data and isinstance(t.input_data, dict):
            positioning = t.input_data.get("positioning", "")
        tasks_data.append({
            "task_id": t.id,
            "positioning_summary": positioning[:50] + ("..." if len(positioning) > 50 else ""),
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "elapsed_seconds": t.elapsed_seconds,
        })

    return ApiResponse(data={
        "tasks": tasks_data,
        "pagination": {"page": page, "page_size": page_size, "total": total},
    })
