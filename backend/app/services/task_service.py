"""Task service: business logic for task lifecycle management."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import TaskNotFoundError, TaskAlreadyRunningError
from app.core.logger import get_logger
from app.core.tracer import generate_task_id, set_task_id
from app.models.tables import TaskModel, TaskNodeRunModel
from app.orchestrator.engine import orchestrator_engine
from app.orchestrator.broadcaster import broadcaster

logger = get_logger(__name__)


class TaskService:

    async def create_task(self, positioning: str, workflow_id: str, db: AsyncSession) -> TaskModel:
        """Create a new task and start the workflow in background."""
        task_id = generate_task_id()
        set_task_id(task_id)

        task = TaskModel(
            id=task_id,
            workflow_id=workflow_id,
            status="pending",
            input_data={"positioning": positioning},
        )
        db.add(task)
        await db.flush()
        logger.info("task_created", task_id=task_id, workflow_id=workflow_id)

        return task

    async def run_task(self, task_id: str, db: AsyncSession) -> None:
        """Run the orchestrator for a task. Called as a background coroutine."""
        task = await self._get_task(task_id, db)
        if task.status == "running":
            raise TaskAlreadyRunningError(task_id)

        try:
            await orchestrator_engine.run(task, db)
            await db.commit()
            logger.info("task_completed", task_id=task_id)
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc)
            if task.started_at:
                task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds()
            db.add(task)
            await db.commit()
            logger.error("task_failed", task_id=task_id, error=str(e))

            await broadcaster.broadcast(task_id, "task_error", {
                "task_id": task_id,
                "error": str(e),
            })
            await broadcaster.close_task(task_id)

    async def get_task(self, task_id: str, db: AsyncSession) -> TaskModel:
        return await self._get_task(task_id, db)

    async def get_task_with_nodes(self, task_id: str, db: AsyncSession) -> TaskModel:
        stmt = (
            select(TaskModel)
            .where(TaskModel.id == task_id)
            .options(selectinload(TaskModel.node_runs))
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def list_tasks(
        self, db: AsyncSession, page: int = 1, page_size: int = 20, status: str | None = None
    ) -> tuple[list[TaskModel], int]:
        """List tasks with pagination."""
        stmt = select(TaskModel).order_by(desc(TaskModel.created_at))
        count_stmt = select(TaskModel)

        if status:
            stmt = stmt.where(TaskModel.status == status)
            count_stmt = count_stmt.where(TaskModel.status == status)

        # Count
        from sqlalchemy import func as sa_func
        count_result = await db.execute(select(sa_func.count()).select_from(count_stmt.subquery()))
        total = count_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await db.execute(stmt)
        tasks = list(result.scalars().all())

        return tasks, total

    async def get_node_runs(self, task_id: str, db: AsyncSession) -> list[TaskNodeRunModel]:
        """Get all node runs for a task."""
        # Verify task exists
        await self._get_task(task_id, db)
        stmt = (
            select(TaskNodeRunModel)
            .where(TaskNodeRunModel.task_id == task_id)
            .order_by(TaskNodeRunModel.id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_task(self, task_id: str, db: AsyncSession) -> TaskModel:
        stmt = select(TaskModel).where(TaskModel.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(task_id)
        return task


task_service = TaskService()
