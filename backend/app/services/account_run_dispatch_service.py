"""Dispatch account-created tasks into background execution."""

from __future__ import annotations

import asyncio

from app.core.logger import get_logger

logger = get_logger(__name__)


class AccountRunDispatchService:
    """Schedule background execution for account-scoped task runs."""

    def __init__(self) -> None:
        self._background_tasks: dict[str, asyncio.Task] = {}

    async def _run_task_in_background(self, task_id: str, account_id: str | None = None) -> None:
        from app.core.tracer import set_task_id
        from app.db.session import async_session_factory
        from app.services.task_service import task_service

        async with async_session_factory() as bg_db:
            try:
                set_task_id(task_id)
                logger.info(
                    "account_run_background_started",
                    account_id=account_id,
                    task_id=task_id,
                )
                await task_service.run_task(task_id, bg_db)
            except Exception:
                import traceback

                traceback.print_exc()
            finally:
                self._background_tasks.pop(task_id, None)

    def schedule(self, *, task_id: str, account_id: str | None = None) -> asyncio.Task:
        task = asyncio.create_task(self._run_task_in_background(task_id, account_id=account_id))
        self._background_tasks[task_id] = task
        logger.info(
            "account_run_background_scheduled",
            account_id=account_id,
            task_id=task_id,
        )
        return task


account_run_dispatch_service = AccountRunDispatchService()
