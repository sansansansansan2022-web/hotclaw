"""
Task Service - 任务服务模块

本模块负责任务生命周期管理的核心业务逻辑，包括：
- 任务创建与初始化
- 任务执行与编排引擎集成
- 任务状态管理与状态转换
- 任务结果处理与草稿生成
- 任务列表查询与分页
- 任务重跑功能

任务状态流转：
- pending -> running -> completed / failed
- completed/failed 可通过 rerun 回到 pending 状态
"""

import asyncio
import builtins
import sys
from datetime import datetime, timezone

from sqlalchemy import select, desc, func as sa_func, delete
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


def _safe_print(*args: object, sep: str = " ", end: str = "\n") -> None:
    text = sep.join(str(arg) for arg in args) + end
    try:
        builtins.print(*args, sep=sep, end=end)
    except UnicodeEncodeError:
        stream = sys.stdout
        encoding = getattr(stream, "encoding", None) or "utf-8"
        buffer = getattr(stream, "buffer", None)
        encoded = text.encode(encoding, errors="backslashreplace")
        if buffer is not None:
            buffer.write(encoded)
        else:
            stream.write(encoded.decode(encoding, errors="ignore"))


print = _safe_print


class TaskService:
    """
    任务服务类

    负责管理任务的完整生命周期，包括创建、执行、状态跟踪和结果处理。
    任务执行通过编排引擎（Orchestrator Engine）进行，支持 E2E 测试模式、超时控制与错误处理。
    """

    async def create_task(self, positioning: str, workflow_id: str, db: AsyncSession) -> TaskModel:
        """
        创建新任务并启动后台工作流。

        Args:
            positioning: 账号定位/选题方向，用于内容生成
            workflow_id: 工作流 ID，指定任务执行的工作流类型
            db: 数据库会话

        Returns:
            TaskModel: 创建的任务实例，状态为 pending
        """
        # 生成唯一任务 ID
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
        """
        执行任务的核心方法。

        此方法作为后台协程运行，负责：
        1. 验证任务状态（仅 pending 状态可执行）
        2. 更新任务状态为 running
        3. 调用编排引擎执行任务
        4. 处理执行结果或异常
        5. 更新任务最终状态（completed/failed）
        6. 生成草稿（根据账号模式）
        7. 更新关联账号的运行状态

        Args:
            task_id: 任务 ID
            db: 数据库会话

        Raises:
            TaskAlreadyRunningError: 任务已在运行中
            HotClawError: 任务状态不是 pending
        """
        # 获取任务实例
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

        # 更新任务状态为运行中
        task.status = "running"
        task.started_at = task.started_at or datetime.now(timezone.utc)
        task.completed_at = None
        task.error_message = None
        db.add(task)
        await db.commit()

        try:
            # 检查是否处于 E2E 测试模式
            generation_mode = await e2e_test_mode_service.get_generation_mode(db)
            simulated = generation_mode == e2e_test_mode_service.MODE_FAKE_SUCCESS
            simulation_source = "e2e_fake" if simulated else None
            provider = "fake" if simulated else self._detect_provider()
            # E2E 失败模式测试
            if generation_mode == e2e_test_mode_service.MODE_FAKE_FAILURE:
                raise RuntimeError(await e2e_test_mode_service.get_generation_failure_message(db))

            if simulated:
                # 模拟模式：使用 E2E 测试服务生成假结果
                input_data = task.input_data if isinstance(task.input_data, dict) else {}
                result_data = e2e_test_mode_service.build_generation_result(
                    task_id=task.id,
                    account_id=task.account_id,
                    positioning=str(input_data.get("positioning") or ""),
                )
                task.status = "completed"
                task.completed_at = datetime.now(timezone.utc)
                task.elapsed_seconds = self.calculate_elapsed_seconds(
                    status=task.status,
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                    elapsed_seconds=None,
                )
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
                # 正常模式：调用编排引擎执行任务
                result_data = await asyncio.wait_for(
                    orchestrator_engine.run(task, db),
                    timeout=task_timeout_seconds,
                )

            # 标准化结果数据
            result_data = article_assembler_service.normalize_result_data(result_data)
            # 确保 ops_context 不丢失
            if isinstance(result_data, dict) and isinstance(task.input_data, dict):
                if "ops_context" not in result_data and isinstance(task.input_data.get("ops_context"), dict):
                    result_data["ops_context"] = task.input_data.get("ops_context")
            # 附加执行元信息
            result_data = self._attach_execution_meta(
                result_data,
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                simulated=simulated,
                simulation_source=simulation_source,
                provider=provider,
                task_status="completed",
                task_id=task_id,
            )
            # 更新任务状态为完成
            if task.status != "completed":
                task.status = "completed"
            if task.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
            task.elapsed_seconds = self.calculate_elapsed_seconds(
                status=task.status,
                started_at=task.started_at,
                completed_at=task.completed_at,
                elapsed_seconds=None,
            )
            task.error_message = None
            task.result_data = result_data
            db.add(task)
            await db.flush()

            # 从任务结果创建草稿（在 commit 前确保原子性）
            # 草稿创建失败不应导致任务失败
            await self._create_draft_from_task_result(task, result_data, db)

            # 一起提交任务结果和草稿
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

            # 如果任务绑定了账号，刷新账号的下次运行时间
            if task.account_id:
                await self._update_account_run_status(task.account_id, db, "success")
                await self._refresh_account_next_run(task.account_id, db)
                # account_service 仅 flush，这里补一次 commit 持久化账号状态
                await db.commit()

        except asyncio.TimeoutError:
            # 任务执行超时处理
            timeout_message = f"task execution timed out after {task_timeout_seconds}s"
            await db.rollback()
            task = await self._get_task(task_id, db)
            timed_out_nodes = await self._mark_running_nodes_failed(task_id, db, timeout_message)
            task.status = "failed"
            task.error_message = timeout_message
            task.completed_at = datetime.now(timezone.utc)
            task.elapsed_seconds = self.calculate_elapsed_seconds(
                status=task.status,
                started_at=task.started_at,
                completed_at=task.completed_at,
                elapsed_seconds=None,
            )
            task.result_data = self._attach_execution_meta(
                task.result_data if isinstance(task.result_data, dict) else {},
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                simulated=False,
                simulation_source=None,
                provider=self._detect_provider(),
                timed_out=True,
                task_status="failed",
                task_id=task_id,
            )
            db.add(task)
            await db.commit()

            # 终端详细日志输出 - 任务超时
            print(f"\n{'='*80}")
            print(f"[TIMEOUT] Task timed out: {task_id}")
            print(f"   状态: FAILED (TIMEOUT)")
            print(f"   总耗时: {task.elapsed_seconds:.2f}s ({task.elapsed_seconds/60:.1f} 分钟)")
            print(f"   超时限制: {task_timeout_seconds}s ({task_timeout_seconds/60:.1f} 分钟)")
            print(f"   错误: {timeout_message}")
            if timed_out_nodes:
                print(f"   超时节点: {', '.join([n['node_id'] for n in timed_out_nodes])}")
            print(f"{'='*80}\n")

            logger.error(
                "task_timed_out",
                task_id=task_id,
                account_id=task.account_id,
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
            )
            for node_event in timed_out_nodes:
                await broadcaster.broadcast(
                    task_id,
                    "node_error",
                    {"node_id": node_event["node_id"], "error": timeout_message},
                )

            # 更新账号运行状态
            if task.account_id:
                await self._update_account_run_status(task.account_id, db, "failed", timeout_message)
                await db.commit()

            # 广播错误事件
            await broadcaster.broadcast(task_id, "task_error", {
                "task_id": task_id,
                "error": timeout_message,
            })
            await broadcaster.close_task(task_id)

        except Exception as e:
            # 其他异常处理
            await db.rollback()
            task = await self._get_task(task_id, db)
            failed_nodes = await self._mark_running_nodes_failed(task_id, db, str(e))
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc)
            task.elapsed_seconds = self.calculate_elapsed_seconds(
                status=task.status,
                started_at=task.started_at,
                completed_at=task.completed_at,
                elapsed_seconds=None,
            )
            task.result_data = self._attach_execution_meta(
                task.result_data if isinstance(task.result_data, dict) else {},
                trace_id=trace_id,
                timeout_seconds=task_timeout_seconds,
                simulated=False,
                simulation_source=None,
                provider=self._detect_provider(),
                task_status="failed",
                task_id=task_id,
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
            for node_event in failed_nodes:
                await broadcaster.broadcast(
                    task_id,
                    "node_error",
                    {"node_id": node_event["node_id"], "error": str(e)},
                )

            # 如果任务绑定了账号，更新账号的运行状态
            if task.account_id:
                await self._update_account_run_status(task.account_id, db, "failed", str(e))
                # account_service 仅 flush，这里补一次 commit 持久化账号失败状态
                await db.commit()

            # 广播错误事件
            await broadcaster.broadcast(task_id, "task_error", {
                "task_id": task_id,
                "error": str(e),
            })
            await broadcaster.close_task(task_id)

    async def get_task(self, task_id: str, db: AsyncSession) -> TaskModel:
        """
        获取任务详情。

        Args:
            task_id: 任务 ID
            db: 数据库会话

        Returns:
            TaskModel: 任务实例

        Raises:
            TaskNotFoundError: 任务不存在
        """
        task = await self._get_task(task_id, db)
        await self._reconcile_task_runtime_state(task, db)
        return task

    async def get_task_with_nodes(self, task_id: str, db: AsyncSession) -> TaskModel:
        """
        获取任务详情及其所有节点运行记录。

        Args:
            task_id: 任务 ID
            db: 数据库会话

        Returns:
            TaskModel: 包含 node_runs 的任务实例
        """
        stmt = (
            select(TaskModel)
            .where(TaskModel.id == task_id)
            .options(selectinload(TaskModel.node_runs))
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise TaskNotFoundError(task_id)
        await self._reconcile_task_runtime_state(task, db)
        return task

    async def list_tasks(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        account_id: str | None = None,
    ) -> tuple[list[TaskModel], int]:
        """
        分页查询任务列表。

        Args:
            db: 数据库会话
            page: 页码（从 1 开始）
            page_size: 每页数量，默认 20
            status: 按任务状态筛选（可选），如 'pending', 'running', 'completed', 'failed'
            account_id: 按账号 ID 筛选（可选）

        Returns:
            tuple[list[TaskModel], int]: (任务列表, 总数)
        """
        stmt = (
            select(TaskModel)
            .options(selectinload(TaskModel.account))
            .order_by(desc(TaskModel.created_at), desc(TaskModel.id))
        )
        count_stmt = select(TaskModel.id)

        # 按状态筛选
        if status:
            stmt = stmt.where(TaskModel.status == status)
            count_stmt = count_stmt.where(TaskModel.status == status)

        # 按账号筛选
        if account_id:
            stmt = stmt.where(TaskModel.account_id == account_id)
            count_stmt = count_stmt.where(TaskModel.account_id == account_id)

        # 查询总数
        count_result = await db.execute(select(sa_func.count()).select_from(count_stmt.subquery()))
        total = count_result.scalar() or 0

        # 分页查询
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
        """
        获取任务的所有节点运行记录。

        Args:
            task_id: 任务 ID
            db: 数据库会话

        Returns:
            list[TaskNodeRunModel]: 按执行顺序排列的节点运行记录列表
        """
        # 先验证任务存在
        task = await self._get_task(task_id, db)
        await self._reconcile_task_runtime_state(task, db)
        stmt = (
            select(TaskNodeRunModel)
            .where(TaskNodeRunModel.task_id == task_id)
            .order_by(TaskNodeRunModel.id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def rerun_task(self, task_id: str, db: AsyncSession) -> TaskModel:
        """
        重置已完成/失败的任务，准备重新执行。

        此方法会：
        1. 删除旧的节点运行记录
        2. 重置任务状态为 pending
        3. 清除结果数据、错误信息、执行时间等

        Args:
            task_id: 任务 ID
            db: 数据库会话

        Returns:
            TaskModel: 重置后的任务实例

        Raises:
            TaskAlreadyRunningError: 任务正在运行中
        """
        task = await self._get_task(task_id, db)
        if task.status == "running":
            raise TaskAlreadyRunningError(task_id)

        # 删除旧的节点运行记录
        await db.execute(
            delete(TaskNodeRunModel).where(TaskNodeRunModel.task_id == task_id)
        )

        # 重置任务状态
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

    async def stop_task(
        self,
        task_id: str,
        db: AsyncSession,
        *,
        reason: str | None = None,
    ) -> tuple[TaskModel, list[dict[str, str]], bool]:
        """Stop an active task and close its currently running nodes."""
        task = await self._get_task(task_id, db)
        if task.status in {"completed", "failed", "cancelled"}:
            return task, [], False

        previous_status = task.status
        message = reason or "task manually stopped"
        closed_nodes = await self._mark_running_nodes_terminal(
            task_id,
            db,
            message,
            terminal_status="cancelled",
        )
        task.status = "cancelled"
        task.error_message = message
        task.completed_at = datetime.now(timezone.utc)
        task.elapsed_seconds = self.calculate_elapsed_seconds(
            status=task.status,
            started_at=task.started_at,
            completed_at=task.completed_at,
            elapsed_seconds=None,
        )
        db.add(task)
        await db.flush()

        if task.account_id:
            await self._update_account_run_status(task.account_id, db, "cancelled", message)

        logger.warning(
            "task_manually_stopped",
            task_id=task_id,
            account_id=task.account_id,
            previous_status=previous_status,
            closed_node_count=len(closed_nodes),
            reason=message,
        )
        return task, closed_nodes, True

    async def delete_task(self, task_id: str, db: AsyncSession) -> dict[str, object]:
        """Delete a task and its task-scoped runtime artifacts."""
        from app.models.tables import (
            AccountProfileModel,
            ArticleDraftModel,
            AuditResultModel,
            EvidenceItemModel,
            SkillInvocationLogModel,
            SystemLogModel,
            TopicCandidateModel,
        )
        from app.models.wechat_config import WeChatPublishRecordModel

        task = await self._get_task(task_id, db)
        previous_status = task.status
        stopped = False
        if task.status in {"pending", "running"}:
            task, _, stopped = await self.stop_task(
                task_id,
                db,
                reason="task deleted before completion",
            )

        draft_id_rows = await db.execute(select(ArticleDraftModel.id).where(ArticleDraftModel.task_id == task_id))
        draft_ids = [row[0] for row in draft_id_rows.all()]
        if draft_ids:
            await db.execute(delete(WeChatPublishRecordModel).where(WeChatPublishRecordModel.draft_id.in_(draft_ids)))
        await db.execute(delete(WeChatPublishRecordModel).where(WeChatPublishRecordModel.task_id == task_id))
        await db.execute(delete(AuditResultModel).where(AuditResultModel.task_id == task_id))
        await db.execute(delete(ArticleDraftModel).where(ArticleDraftModel.task_id == task_id))
        await db.execute(delete(AccountProfileModel).where(AccountProfileModel.task_id == task_id))
        await db.execute(delete(TopicCandidateModel).where(TopicCandidateModel.task_id == task_id))
        await db.execute(delete(TaskNodeRunModel).where(TaskNodeRunModel.task_id == task_id))
        await db.execute(delete(EvidenceItemModel).where(EvidenceItemModel.task_id == task_id))
        await db.execute(delete(SkillInvocationLogModel).where(SkillInvocationLogModel.task_id == task_id))
        await db.execute(delete(SystemLogModel).where(SystemLogModel.task_id == task_id))
        await db.delete(task)
        await db.flush()

        logger.warning(
            "task_deleted",
            task_id=task_id,
            previous_status=previous_status,
            stopped_before_delete=stopped,
        )
        return {
            "task_id": task_id,
            "deleted": True,
            "previous_status": previous_status,
            "stopped_before_delete": stopped,
        }

    async def _get_task(self, task_id: str, db: AsyncSession) -> TaskModel:
        """
        内部方法：获取任务实例（包含关联的账号信息）。

        Args:
            task_id: 任务 ID
            db: 数据库会话

        Returns:
            TaskModel: 任务实例

        Raises:
            TaskNotFoundError: 任务不存在
        """
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

    def calculate_elapsed_seconds(
        self,
        *,
        status: str,
        started_at: datetime | None,
        completed_at: datetime | None,
        elapsed_seconds: float | None,
    ) -> float | None:
        """Return persisted elapsed seconds or a live fallback for in-flight records."""
        if elapsed_seconds is not None:
            return elapsed_seconds

        started = self._ensure_utc(started_at)
        if started is None:
            return None

        completed = self._ensure_utc(completed_at)
        if completed is not None:
            return max((completed - started).total_seconds(), 0.0)

        if status in {"pending", "running"}:
            return max((datetime.now(timezone.utc) - started).total_seconds(), 0.0)

        return None

    async def _refresh_account_next_run(self, account_id: str, db: AsyncSession) -> None:
        """
        内部方法：任务完成后刷新账号的下次运行时间。

        Args:
            account_id: 账号 ID
            db: 数据库会话
        """
        try:
            from app.services.account_service import account_service
            await account_service.refresh_next_run(account_id, db)
            logger.info("account_next_run_refreshed_after_task", account_id=account_id)
        except Exception as e:
            logger.warning("failed_to_refresh_account_next_run", account_id=account_id, error=str(e))

    def _ensure_utc(self, dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    async def _update_account_run_status(
        self, account_id: str, db: AsyncSession, status: str, error_message: str | None = None
    ) -> None:
        """
        内部方法：更新账号的运行状态。

        在任务完成（成功或失败）后调用，同步更新账号的运行状态信息。

        Args:
            account_id: 账号 ID
            db: 数据库会话
            status: 运行状态，'success' | 'failed' | 'cancelled'
            error_message: 错误信息（任务失败时提供）
        """
        try:
            from app.services.account_service import account_service
            await account_service.update_account_run_status(account_id, db, status, error_message)
            logger.info("account_run_status_updated", account_id=account_id, status=status)
        except Exception as e:
            logger.warning("failed_to_update_account_run_status", account_id=account_id, error=str(e))

    async def _reconcile_task_runtime_state(self, task: TaskModel, db: AsyncSession) -> None:
        """Repair stale task/node state left behind by interrupted workers or old bugs."""
        changed = False

        if task.status in {"completed", "failed", "cancelled"}:
            terminal_message = task.error_message or f"task already {task.status}"
            closed_nodes = await self._mark_running_nodes_terminal(
                task.id,
                db,
                terminal_message,
                terminal_status="cancelled" if task.status == "cancelled" else "failed",
            )
            changed = bool(closed_nodes)
        elif task.status == "running":
            timeout_seconds = self._get_task_timeout_seconds()
            live_elapsed = self.calculate_elapsed_seconds(
                status=task.status,
                started_at=task.started_at,
                completed_at=task.completed_at,
                elapsed_seconds=task.elapsed_seconds,
            )
            if live_elapsed is not None and live_elapsed >= timeout_seconds:
                timeout_message = f"task execution timed out after {timeout_seconds}s"
                timed_out_nodes = await self._mark_running_nodes_failed(task.id, db, timeout_message)
                task.status = "failed"
                task.error_message = timeout_message
                task.completed_at = datetime.now(timezone.utc)
                task.elapsed_seconds = self.calculate_elapsed_seconds(
                    status="failed",
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                    elapsed_seconds=None,
                )
                task.result_data = self._attach_execution_meta(
                    task.result_data if isinstance(task.result_data, dict) else {},
                    trace_id=get_trace_id() or generate_trace_id(),
                    timeout_seconds=timeout_seconds,
                    simulated=False,
                    simulation_source=None,
                    provider=self._detect_provider(),
                    timed_out=True,
                    task_status="failed",
                    task_id=task.id,
                )
                db.add(task)
                changed = True
                if task.account_id:
                    await self._update_account_run_status(task.account_id, db, "failed", timeout_message)
                logger.warning(
                    "stale_running_task_reconciled",
                    task_id=task.id,
                    account_id=task.account_id,
                    timeout_seconds=timeout_seconds,
                    node_count=len(timed_out_nodes),
                )

        if changed:
            await db.commit()

    async def recover_interrupted_active_tasks(
        self,
        db: AsyncSession,
        *,
        reason: str = "task interrupted by backend restart",
    ) -> int:
        """Fail active tasks that cannot be resumed after an in-process worker restart."""
        result = await db.execute(
            select(TaskModel).where(TaskModel.status.in_(["pending", "running"]))
        )
        active_tasks = list(result.scalars().all())
        if not active_tasks:
            return 0

        completed_at = datetime.now(timezone.utc)
        timeout_seconds = self._get_task_timeout_seconds()
        recovered_count = 0

        for task in active_tasks:
            previous_status = task.status
            closed_nodes = await self._mark_running_nodes_terminal(
                task.id,
                db,
                reason,
                terminal_status="failed",
            )
            task.status = "failed"
            task.error_message = reason
            task.completed_at = completed_at
            task.elapsed_seconds = self.calculate_elapsed_seconds(
                status="failed",
                started_at=task.started_at,
                completed_at=completed_at,
                elapsed_seconds=None,
            )
            task.result_data = self._attach_execution_meta(
                task.result_data if isinstance(task.result_data, dict) else {},
                trace_id=get_trace_id() or generate_trace_id(),
                timeout_seconds=timeout_seconds,
                simulated=False,
                simulation_source=None,
                provider=self._detect_provider(),
                timed_out=False,
                task_status="failed",
                task_id=task.id,
            )
            db.add(task)
            recovered_count += 1

            if task.account_id:
                await self._update_account_run_status(task.account_id, db, "failed", reason)

            logger.warning(
                "interrupted_active_task_recovered",
                task_id=task.id,
                account_id=task.account_id,
                previous_status=previous_status,
                closed_node_count=len(closed_nodes),
                reason=reason,
            )

        await db.commit()
        return recovered_count

    async def _mark_running_nodes_failed(
        self,
        task_id: str,
        db: AsyncSession,
        error_message: str,
    ) -> list[dict[str, str]]:
        """Close node rows left in running state after a task-level failure."""
        return await self._mark_running_nodes_terminal(
            task_id,
            db,
            error_message,
            terminal_status="failed",
        )

    async def _mark_running_nodes_terminal(
        self,
        task_id: str,
        db: AsyncSession,
        error_message: str,
        *,
        terminal_status: str,
    ) -> list[dict[str, str]]:
        """Close node rows left in running state after a task-level terminal transition."""
        result = await db.execute(
            select(TaskNodeRunModel).where(
                TaskNodeRunModel.task_id == task_id,
                TaskNodeRunModel.status == "running",
            )
        )
        running_nodes = list(result.scalars().all())
        if not running_nodes:
            return []

        completed_at = datetime.now(timezone.utc)
        events: list[dict[str, str]] = []
        for node in running_nodes:
            started_at = node.started_at
            if started_at is not None and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            node.status = terminal_status
            node.error_message = error_message
            node.completed_at = completed_at
            node.elapsed_seconds = self.calculate_elapsed_seconds(
                status=node.status,
                started_at=started_at,
                completed_at=completed_at,
                elapsed_seconds=None,
            )
            db.add(node)
            events.append({"node_id": node.node_id, "agent_id": node.agent_id})

        await db.flush()
        logger.warning(
            "task_running_nodes_marked_failed",
            task_id=task_id,
            terminal_status=terminal_status,
            count=len(events),
            error=error_message,
            node_ids=[event["node_id"] for event in events],
        )
        return events

    async def _create_draft_from_task_result(
        self, task: TaskModel, result_data: dict, db: AsyncSession
    ) -> None:
        """
        内部方法：从任务结果创建草稿。

        根据账号运营模式决定草稿状态：
        - full_auto: 草稿状态为 'approved'（自动批准）
        - semi_auto: 草稿状态为 'pending_review'（待审核）
        - manual: 草稿状态为 'draft'（草稿）

        如果是 full_auto 模式且允许自动发布，会触发自动发布到微信。

        Args:
            task: 任务实例
            result_data: 编排引擎返回的结果数据
            db: 数据库会话
        """
        try:
            from app.services.draft_service import draft_service
            from app.services.automation_plan_service import automation_plan_service
            from app.services.draft_quality_gate_service import draft_quality_gate_service

            # 标准化结果数据
            result_data = article_assembler_service.normalize_result_data(result_data)

            # 获取账号运营模式
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

            # 创建草稿
            draft = await draft_service.create_draft_from_task(
                task_id=task.id,
                result_data=result_data,
                account_id=task.account_id,
                operation_mode=operation_mode,
                db=db
            )
            gate_result = await draft_quality_gate_service.persist_for_draft(
                draft=draft,
                result_data=result_data,
                db=db,
            )
            task.result_data = result_data
            db.add(task)
            if not gate_result.get("passed"):
                auto_publish_enabled = False
            logger.info(
                "draft_created_from_task",
                task_id=task.id,
                draft_id=draft.id,
                draft_status=draft.draft_status,
                effective_mode=operation_mode,
                allow_auto_publish=auto_publish_enabled,
                quality_gate_passed=gate_result.get("passed"),
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
            # 草稿创建失败不应导致任务失败
            logger.error("draft_creation_failed", task_id=task.id, error=str(e))

    def _get_task_timeout_seconds(self) -> int:
        """
        计算任务超时时间。

        根据编排引擎中的工作流节点数量和配置的超时设置计算最大超时时间。

        Returns:
            int: 超时时间（秒）
        """
        configured_budget = int(getattr(settings, "task_timeout_seconds", 600) or 600)
        return max(configured_budget, 600, settings.agent_timeout + 30)

    def _detect_provider(self) -> str:
        """
        从模型名称中检测 LLM 提供商。

        如果模型名称包含 "/"（如 "dashscope/qwen-turbo"），提取 "/" 前的部分作为提供商。

        Returns:
            str: 提供商名称，默认 "dashscope"
        """
        model_name = settings.llm_model_name.strip()
        if "/" in model_name:
            return model_name.split("/", 1)[0]
        return "dashscope"

    def _is_degraded_result(self, result_data: dict | None) -> bool:
        """
        检查结果是否是降级模式（部分节点失败）。

        检查 content_pipeline 中是否标记为 degraded。

        Args:
            result_data: 任务结果数据

        Returns:
            bool: 是否为降级结果
        """
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
        task_status: str | None = None,
        task_id: str | None = None,
    ) -> dict:
        """
        为结果数据附加执行元信息。

        Args:
            result_data: 原始结果数据
            trace_id: 追踪 ID
            timeout_seconds: 任务超时设置（秒）
            simulated: 是否为模拟执行
            simulation_source: 模拟来源（E2E 测试模式）
            provider: LLM 提供商
            timed_out: 是否超时

        Returns:
            dict: 包含 execution_meta 的结果数据
        """
        payload = dict(result_data or {})
        existing = payload.get("execution_meta")
        execution_meta = dict(existing) if isinstance(existing, dict) else {}
        existing_degraded = execution_meta.get("degraded")
        if isinstance(existing_degraded, bool):
            degraded_value = existing_degraded
        else:
            degraded_value = self._is_degraded_result(payload)
        execution_meta.update(
            {
                "trace_id": trace_id,
                "task_timeout_seconds": timeout_seconds,
                "simulated": simulated,
                "simulation_source": simulation_source,
                "provider": provider,
                "timed_out": timed_out,
                "degraded": degraded_value,
            }
        )
        execution_meta.setdefault("single_gate_mode", True)
        if "publishability" not in execution_meta:
            if task_status == "completed":
                execution_meta["publishability"] = "publishable"
            elif task_status in {"failed", "cancelled"}:
                execution_meta["publishability"] = "blocked"
            else:
                execution_meta["publishability"] = "unknown"
        if not isinstance(execution_meta.get("stages"), list):
            execution_meta["stages"] = []
        if task_status in {"failed", "cancelled"} and not execution_meta["stages"]:
            execution_meta["stages"].append(
                {
                    "trace_id": trace_id,
                    "task_id": task_id,
                    "stage": "terminal_task_status",
                    "status": "hard_fail",
                    "severity": "blocker",
                    "attempt": 1,
                    "max_attempts": 1,
                    "model_route": {"provider": provider, "model": None, "fallback_used": False},
                    "error": {"code": "task_failed", "message": None, "retry_after_ms": 0},
                    "next_action": "stop",
                }
            )
        payload["execution_meta"] = execution_meta
        return payload


task_service = TaskService()
