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
            # Run the orchestrator
            result_data = await orchestrator_engine.run(task, db)

            # Create draft from task result BEFORE commit to ensure atomicity
            # Draft creation failure should not fail the task
            await self._create_draft_from_task_result(task, result_data, db)

            # Commit task result and draft together
            await db.commit()
            logger.info("task_completed", task_id=task_id)

            # If this task is bound to an account, refresh the account's next_run_at
            if task.account_id:
                await self._refresh_account_next_run(task.account_id, db)

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc)
            if task.started_at:
                task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds()
            db.add(task)
            await db.commit()
            logger.error("task_failed", task_id=task_id, error=str(e))

            # If this task is bound to an account, update the account's run status
            if task.account_id:
                await self._update_account_run_status_on_failure(task.account_id, db, str(e))

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

    async def rerun_task(self, task_id: str, db: AsyncSession) -> TaskModel:
        """Reset a completed/failed task and prepare it for re-execution."""
        task = await self._get_task(task_id, db)
        if task.status == "running":
            raise TaskAlreadyRunningError(task_id)

        # Delete old node runs
        from sqlalchemy import delete
        await db.execute(
            delete(TaskNodeRunModel).where(TaskNodeRunModel.task_id == task_id)
        )

        # Reset task state
        task.status = "pending"
        task.result_data = None
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        task.elapsed_seconds = None
        task.total_tokens = None
        db.add(task)
        await db.flush()
        logger.info("task_rerun_prepared", task_id=task_id)

        return task

    async def _get_task(self, task_id: str, db: AsyncSession) -> TaskModel:
        stmt = select(TaskModel).where(TaskModel.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    async def _refresh_account_next_run(self, account_id: str, db: AsyncSession) -> None:
        """Refresh account's next_run_at after task completion."""
        try:
            from app.services.account_service import account_service
            await account_service.refresh_next_run(account_id, db)
            logger.info("account_next_run_refreshed_after_task", account_id=account_id)
        except Exception as e:
            logger.warning("failed_to_refresh_account_next_run", account_id=account_id, error=str(e))

    async def _update_account_run_status_on_failure(
        self, account_id: str, db: AsyncSession, error_message: str
    ) -> None:
        """Update account's run status after task failure."""
        try:
            from app.services.account_service import account_service
            await account_service.update_account_run_status(account_id, db, "failed", error_message)
            logger.info("account_run_status_updated_on_failure", account_id=account_id)
        except Exception as e:
            logger.warning("failed_to_update_account_run_status", account_id=account_id, error=str(e))

    async def _create_draft_from_task_result(
        self, task: TaskModel, result_data: dict, db: AsyncSession
    ) -> None:
        """
        Create a draft from task result data.

        For semi_auto accounts, draft will be in 'pending_review' status.
        For manual accounts, draft will be in 'draft' status.

        This method is called after task completion.
        """
        try:
            from app.services.draft_service import draft_service

            # Get account operation mode if account_id exists
            operation_mode = None
            if task.account_id:
                from sqlalchemy import select
                from app.models.tables import AccountModel
                stmt = select(AccountModel.operation_mode).where(AccountModel.id == task.account_id)
                result = await db.execute(stmt)
                operation_mode = result.scalar_one_or_none()

            draft = await draft_service.create_draft_from_task(
                task_id=task.id,
                result_data=result_data,
                account_id=task.account_id,
                operation_mode=operation_mode,
                db=db
            )
            logger.info(
                "draft_created_from_task",
                task_id=task.id,
                draft_id=draft.id,
                draft_status=draft.draft_status
            )
        except Exception as e:
            # Draft creation failure should not fail the task
            logger.error("draft_creation_failed", task_id=task.id, error=str(e))


task_service = TaskService()
