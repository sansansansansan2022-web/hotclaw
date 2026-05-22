"""
Account Scheduler - background task for auto-running accounts.

【账号定时调度器】
后台服务，定期扫描满足条件的账号并自动触发任务执行。

联动模块：
- Service: app.services.account_service (获取待执行账号、更新运行状态)
- Service: app.services.task_service (运行任务)
- Orchestrator: app.orchestrator.engine (执行编排引擎)
- DB: app.db.session (独立数据库会话)

启动方式：
- 在 app.main.py 的 lifespan 中调用 account_scheduler.start()
- 应用关闭时自动调用 account_scheduler.stop()

调度逻辑：
1. 每 60 秒执行一次扫描（SCHEDULER_INTERVAL）
2. 调用 account_service.get_due_accounts() 获取符合条件的账号
3. 二次验收账号状态（is_active, auto_run_enabled, operation_mode）
4. 使用 Semaphore 限制并发数（MAX_CONCURRENT_RUNS=3）
5. 为每个账号创建独立后台任务执行

账号验收条件：
- is_active == True (账号已启用)
- auto_run_enabled == True (定时运行已开启)
- operation_mode in ("semi_auto", "full_auto") (非 manual 模式)
- next_run_at <= now (已到执行时间)
- 当前没有 pending/running 状态的任务 (防重复)

任务完成后：
- 更新账号运行状态 (last_run_status = "success" / "failed")
- 记录错误信息 (last_error_message)
- 重新计算下次执行时间 (next_run_at)
"""

import asyncio
from datetime import datetime, timezone

from app.core.logger import get_logger
from app.core.tracer import set_trace_id, generate_trace_id, generate_task_id
from app.core.exceptions import (
    AccountNotFoundError,
    AccountInactiveError,
    AccountValidationError,
    TaskAlreadyExistsError,
    TaskCreateError,
)

logger = get_logger(__name__)

# Scheduler interval in seconds
# 【调度间隔】每 60 秒扫描一次待执行账号
SCHEDULER_INTERVAL = 60

# Max concurrent account runs to prevent overwhelming the system
# 【并发限制】最多同时运行 3 个账号任务，防止系统过载
MAX_CONCURRENT_RUNS = 3


class AccountScheduler:
    """
    Background scheduler that checks for due accounts and triggers runs.

    【定时调度器】
    定期检查所有 auto_run_enabled 的账号，
    当 next_run_at 已过期且满足条件的账号时，自动触发任务执行。

    验收逻辑：
    1. is_active == True
    2. auto_run_enabled == True
    3. operation_mode in ("semi_auto", "full_auto")
    4. next_run_at <= now
    5. 账号当前没有 pending/running 任务
    """

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_RUNS)

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            logger.warning("scheduler_already_running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("account_scheduler_started", interval=SCHEDULER_INTERVAL)

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("account_scheduler_stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop with error isolation."""
        while self._running:
            try:
                await self._check_and_run_due_accounts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Scheduler tick error should not crash the service
                logger.error("scheduler_tick_error", error=str(e), error_type=type(e).__name__)
            await asyncio.sleep(SCHEDULER_INTERVAL)

    async def _check_and_run_due_accounts(self) -> None:
        """
        Check for due accounts and trigger runs.

        【核心逻辑】
        1. 调用 account_service.get_due_accounts() 获取需要执行的账号
           - 已在 service 层过滤：is_active, auto_run_enabled, operation_mode, next_run_at
        2. 为每个账号创建后台任务执行（带并发限制）
        """
        from app.db.session import async_session_factory
        from app.services.account_service import account_service

        async with async_session_factory() as db:
            due_accounts = await account_service.get_due_accounts(db)
            await db.commit()

        if not due_accounts:
            return

        logger.info("scheduler_tick", due_account_count=len(due_accounts))

        for account in due_accounts:
            # Check eligibility one more time before scheduling
            if not self._is_eligible_for_auto_run(account):
                logger.info(
                    "account_skipped",
                    account_id=account.id,
                    reason="ineligible for auto run",
                    is_active=account.is_active,
                    auto_run_enabled=account.auto_run_enabled,
                    operation_mode=account.operation_mode
                )
                continue

            # Use semaphore to limit concurrent runs
            asyncio.create_task(self._run_account_task_limited(account.id))

    def _is_eligible_for_auto_run(self, account) -> bool:
        """
        Final eligibility check before scheduling.
        This is a defensive check - main filtering is in get_due_accounts.
        """
        # Must be active
        if not account.is_active:
            return False
        # Must have auto run enabled
        if not account.auto_run_enabled:
            return False
        # Must be semi_auto or full_auto (not manual)
        if account.operation_mode == "manual":
            return False
        # Must have next_run_at set
        if not account.next_run_at:
            return False
        # Must be past next_run_at
        now = datetime.now(timezone.utc)
        if account.next_run_at > now:
            return False
        return True

    async def _run_account_task_limited(self, account_id: str) -> None:
        """Run account task with semaphore to limit concurrency."""
        async with self._semaphore:
            await self._run_account_task(account_id)

    async def _run_account_task(self, account_id: str) -> None:
        """
        Run a single account task in background.

        【独立后台任务】
        每个账号的执行都是独立的，不影响其他账号和主请求。
        使用单独的 db session 确保事务隔离。
        """
        from app.db.session import async_session_factory
        from app.services.account_service import account_service
        from app.services.task_service import task_service
        from app.orchestrator.engine import orchestrator_engine

        trace_id = generate_trace_id()
        set_trace_id(trace_id)

        logger.info("account_scheduler_triggered", account_id=account_id, trace_id=trace_id)

        async with async_session_factory() as db:
            try:
                # Trigger account run with allow_auto=True for scheduler
                account, task = await account_service.run_account(account_id, db, allow_auto=True)
                await db.commit()

                logger.info(
                    "account_auto_run_started",
                    account_id=account_id,
                    task_id=task.id,
                    operation_mode=account.operation_mode
                )

                # Run the task
                try:
                    await task_service.run_task(task.id, db)
                    await db.refresh(task)
                    if task.status == "failed":
                        logger.error(
                            "account_task_failed",
                            account_id=account_id,
                            task_id=task.id,
                            error=task.error_message or "task failed",
                        )
                        return
                except Exception as task_error:
                    # Task failed - update status with error
                    error_msg = str(task_error)
                    logger.error(
                        "account_task_failed",
                        account_id=account_id,
                        task_id=task.id,
                        error=error_msg
                    )
                    await account_service.update_account_run_status(
                        account_id, db, "failed", error_msg
                    )
                    # Re-raise to update task status
                    raise

                logger.info(
                    "account_auto_run_completed",
                    account_id=account_id,
                    task_id=task.id
                )

            except TaskAlreadyExistsError as e:
                # Another task is running, skip this tick
                # This can happen if scheduler tick happens while previous run is still in progress
                logger.info(
                    "account_skip_already_running",
                    account_id=account_id,
                    existing_task_id=e.details.get("task_id"),
                    reason="another task is still running"
                )
                # Don't update status - task is still running, next_run_at will be refreshed when it completes

            except (AccountNotFoundError, AccountInactiveError, AccountValidationError) as e:
                # Account state changed, log and skip
                logger.warning(
                    "account_scheduler_account_error",
                    account_id=account_id,
                    error=e.message,
                    error_code=e.code
                )

            except TaskCreateError as e:
                # Failed to create task, update status with error
                logger.error(
                    "account_scheduler_task_create_error",
                    account_id=account_id,
                    error=e.message
                )
                try:
                    await account_service.update_account_run_status(
                        account_id, db, "failed", f"任务创建失败: {e.message}"
                    )
                    await db.commit()
                except Exception:
                    pass  # Best effort

            except Exception as e:
                # Unexpected error, log and update status
                logger.error(
                    "account_scheduler_unexpected_error",
                    account_id=account_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                try:
                    await account_service.update_account_run_status(
                        account_id, db, "failed", f"调度异常: {str(e)[:200]}"
                    )
                    await db.commit()
                except Exception:
                    pass  # Best effort


# Global scheduler instance
account_scheduler = AccountScheduler()
