"""Task service: business logic for task lifecycle management."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, desc, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import TaskNotFoundError, TaskAlreadyRunningError, HotClawError
from app.core.logger import get_logger
from app.core.tracer import generate_task_id, set_task_id, get_trace_id, generate_trace_id, set_trace_id
from app.models.tables import TaskModel, TaskNodeRunModel
from app.orchestrator.engine import orchestrator_engine
from app.orchestrator.broadcaster import broadcaster
from app.services.account_harness_service import account_harness_service
from app.services.article_assembler_service import article_assembler_service
from app.services.e2e_test_mode_service import e2e_test_mode_service

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
        set_task_id(task_id)
        trace_id = get_trace_id() or generate_trace_id()
        set_trace_id(trace_id)
        task_timeout_seconds = self._get_task_timeout_seconds()
        # 仅允许 pending 任务进入执行，避免重复跑已完成/失败任务
        if task.status == "running":
            raise TaskAlreadyRunningError(task_id)
        if task.status != "pending":
            raise HotClawError(
                code=2003,
                message=f"task is not pending: {task_id}",
                details={"status": task.status},
            )

        task.status = "running"
        task.started_at = task.started_at or datetime.now(timezone.utc)
        task.completed_at = None
        task.error_message = None
        db.add(task)
        await db.commit()
        logger.info(
            "task_execution_started",
            task_id=task.id,
            account_id=task.account_id,
            trace_id=trace_id,
            timeout_seconds=task_timeout_seconds,
        )

        try:
            generation_mode = await e2e_test_mode_service.get_generation_mode(db)
            simulated = generation_mode == e2e_test_mode_service.MODE_FAKE_SUCCESS
            simulation_source = "e2e_fake" if simulated else None
            provider = "fake" if simulated else self._detect_provider()
            if generation_mode == e2e_test_mode_service.MODE_FAKE_FAILURE:
                raise RuntimeError(await e2e_test_mode_service.get_generation_failure_message(db))

            if simulated:
                input_data = task.input_data if isinstance(task.input_data, dict) else {}
                result_data = e2e_test_mode_service.build_generation_result(
                    task_id=task.id,
                    account_id=task.account_id,
                    positioning=str(input_data.get("positioning") or ""),
                )
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds() if task.started_at else None
                task.total_tokens = 0
                db.add(task)
                await db.flush()
                await broadcaster.broadcast(
                    task.id,
                    "task_complete",
                    {
                        "task_id": task.id,
                        "elapsed_seconds": task.elapsed_seconds,
                    },
                )
                await broadcaster.close_task(task.id)
            else:
                result_data = await asyncio.wait_for(
                    orchestrator_engine.run(task, db),
                    timeout=task_timeout_seconds,
                )

            result_data = article_assembler_service.normalize_result_data(result_data)
            if isinstance(result_data, dict) and isinstance(task.input_data, dict):
                if "ops_context" not in result_data and isinstance(task.input_data.get("ops_context"), dict):
                    result_data["ops_context"] = task.input_data.get("ops_context")
            result_data = self._attach_execution_meta(
                result_data,
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                simulated=simulated,
                simulation_source=simulation_source,
                provider=provider,
            )
            if task.status != "completed":
                task.status = "completed"
            if task.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
            if task.started_at and task.completed_at:
                task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds()
            task.error_message = None
            task.result_data = result_data
            db.add(task)
            await db.flush()

            # Create draft from task result BEFORE commit to ensure atomicity
            # Draft creation failure should not fail the task
            await self._create_draft_from_task_result(task, result_data, db)

            # Commit task result and draft together
            await db.commit()
            logger.info(
                "task_completed",
                task_id=task_id,
                account_id=task.account_id,
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                degraded=self._is_degraded_result(result_data),
                simulated=simulated,
                provider=provider,
            )

            # If this task is bound to an account, refresh the account's next_run_at
            if task.account_id:
                await self._update_account_run_status(task.account_id, db, "success")
                await self._refresh_account_next_run(task.account_id, db)
                # account_service 仅 flush，这里补一次 commit 持久化账号状态
                await db.commit()

        except asyncio.TimeoutError:
            timeout_message = f"task execution timed out after {task_timeout_seconds}s"
            task.status = "failed"
            task.error_message = timeout_message
            task.completed_at = datetime.now(timezone.utc)
            if task.started_at:
                task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds()
            task.result_data = self._attach_execution_meta(
                task.result_data if isinstance(task.result_data, dict) else {},
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                simulated=False,
                simulation_source=None,
                provider=self._detect_provider(),
                timed_out=True,
            )
            db.add(task)
            await db.commit()
            logger.error(
                "task_timed_out",
                task_id=task_id,
                account_id=task.account_id,
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
            )

            if task.account_id:
                await self._update_account_run_status(task.account_id, db, "failed", timeout_message)
                await db.commit()

            await broadcaster.broadcast(task_id, "task_error", {
                "task_id": task_id,
                "error": timeout_message,
            })
            await broadcaster.close_task(task_id)

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc)
            if task.started_at:
                task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds()
            task.result_data = self._attach_execution_meta(
                task.result_data if isinstance(task.result_data, dict) else {},
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                simulated=False,
                simulation_source=None,
                provider=self._detect_provider(),
            )
            db.add(task)
            await db.commit()
            logger.error(
                "task_failed",
                task_id=task_id,
                account_id=task.account_id,
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                error=str(e),
            )

            # If this task is bound to an account, update the account's run status
            if task.account_id:
                await self._update_account_run_status(task.account_id, db, "failed", str(e))
                # account_service 仅 flush，这里补一次 commit 持久化账号失败状态
                await db.commit()

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
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        account_id: str | None = None,
    ) -> tuple[list[TaskModel], int]:
        """List tasks with pagination."""
        stmt = (
            select(TaskModel)
            .options(selectinload(TaskModel.account))
            .order_by(desc(TaskModel.created_at), desc(TaskModel.id))
        )
        count_stmt = select(TaskModel.id)

        if status:
            stmt = stmt.where(TaskModel.status == status)
            count_stmt = count_stmt.where(TaskModel.status == status)

        if account_id:
            stmt = stmt.where(TaskModel.account_id == account_id)
            count_stmt = count_stmt.where(TaskModel.account_id == account_id)

        # Count
        count_result = await db.execute(select(sa_func.count()).select_from(count_stmt.subquery()))
        total = count_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await db.execute(stmt)
        tasks = list(result.scalars().all())

        logger.info(
            "task_list_loaded",
            account_id=account_id,
            status=status,
            page=page,
            page_size=page_size,
            returned=len(tasks),
            total=total,
        )

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
        stmt = (
            select(TaskModel)
            .where(TaskModel.id == task_id)
            .options(selectinload(TaskModel.account))
        )
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

    async def _update_account_run_status(
        self, account_id: str, db: AsyncSession, status: str, error_message: str | None = None
    ) -> None:
        """Update account's run status after task completion/failure."""
        try:
            from app.services.account_service import account_service
            await account_service.update_account_run_status(account_id, db, status, error_message)
            logger.info("account_run_status_updated", account_id=account_id, status=status)
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
            from app.services.automation_plan_service import automation_plan_service

            result_data = article_assembler_service.normalize_result_data(result_data)

            # Get account operation mode if account_id exists
            operation_mode = None
            auto_publish_enabled = False
            ops_context = account_harness_service.extract_ops_context(task.input_data, result_data)
            run_strategy = ops_context.get("run_strategy") if isinstance(ops_context, dict) else {}
            if task.account_id:
                from app.models.tables import AccountModel
                stmt = select(AccountModel).where(AccountModel.id == task.account_id)
                result = await db.execute(stmt)
                account = result.scalar_one_or_none()
                if account is not None:
                    summary = await automation_plan_service.get_effective_summary(account, db)
                    operation_mode = (
                        run_strategy.get("effective_mode")
                        if isinstance(run_strategy, dict) and run_strategy.get("effective_mode")
                        else summary.get("plan_type")
                    )
                    auto_publish_enabled = (
                        bool(run_strategy.get("allow_auto_publish"))
                        if isinstance(run_strategy, dict) and "allow_auto_publish" in run_strategy
                        else bool(summary.get("auto_publish_enabled"))
                    )
            elif isinstance(run_strategy, dict):
                operation_mode = run_strategy.get("effective_mode")
                auto_publish_enabled = bool(run_strategy.get("allow_auto_publish"))

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
                draft_status=draft.draft_status,
                effective_mode=operation_mode,
                allow_auto_publish=auto_publish_enabled,
            )

            # full_auto: 尝试自动发布到微信（不影响任务主流程）
            if task.account_id and operation_mode == "full_auto" and auto_publish_enabled:
                try:
                    published_draft, _ = await draft_service.publish_to_wechat(
                        draft_id=draft.id,
                        db=db,
                        confirmed_by="system",
                        source_mode="full_auto",
                        trigger_type="full_auto",
                    )
                    logger.info(
                        "full_auto_publish_completed",
                        task_id=task.id,
                        draft_id=published_draft.id,
                        publish_status=published_draft.publish_status,
                    )
                except Exception as e:
                    # 自动发布失败不应影响任务已完成状态，保留草稿供后续人工处理
                    logger.error(
                        "full_auto_publish_failed",
                        task_id=task.id,
                        draft_id=draft.id,
                        error=str(e),
                    )
        except Exception as e:
            # Draft creation failure should not fail the task
            logger.error("draft_creation_failed", task_id=task.id, error=str(e))

    def _get_task_timeout_seconds(self) -> int:
        node_count = max(orchestrator_engine.get_workflow_node_count(), 1)
        per_node_budget = settings.agent_timeout * node_count + 30
        bounded_total_budget = settings.agent_timeout + settings.llm_timeout + 30
        return max(min(per_node_budget, bounded_total_budget), settings.agent_timeout + 30)

    def _detect_provider(self) -> str:
        model_name = settings.llm_model_name.strip()
        if "/" in model_name:
            return model_name.split("/", 1)[0]
        return "dashscope"

    def _is_degraded_result(self, result_data: dict | None) -> bool:
        if not isinstance(result_data, dict):
            return False
        content_pipeline = result_data.get("content_pipeline")
        return bool(isinstance(content_pipeline, dict) and content_pipeline.get("degraded"))

    def _attach_execution_meta(
        self,
        result_data: dict | None,
        *,
        trace_id: str,
        timeout_seconds: int,
        simulated: bool,
        simulation_source: str | None,
        provider: str | None,
        timed_out: bool = False,
    ) -> dict:
        payload = dict(result_data or {})
        existing = payload.get("execution_meta")
        execution_meta = dict(existing) if isinstance(existing, dict) else {}
        execution_meta.update(
            {
                "trace_id": trace_id,
                "task_timeout_seconds": timeout_seconds,
                "simulated": simulated,
                "simulation_source": simulation_source,
                "provider": provider,
                "timed_out": timed_out,
                "degraded": self._is_degraded_result(payload),
            }
        )
        payload["execution_meta"] = execution_meta
        return payload


task_service = TaskService()
