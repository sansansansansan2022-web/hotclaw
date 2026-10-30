"""Regression tests for the scheduler's final eligibility and task dispatch."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.scheduler.account_scheduler import AccountScheduler


def test_eligible_plan_is_not_rejected_by_stale_account_mirror():
    scheduler = AccountScheduler()
    account = SimpleNamespace(
        is_active=True,
        operation_mode="manual",
        auto_run_enabled=False,
        next_run_at=None,
    )
    summary = {
        "plan_type": "semi_auto",
        "is_enabled": True,
        "run_strategy": "scheduled",
        "next_run_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    }

    assert scheduler._is_eligible_for_auto_run(account, summary)


def test_sqlite_naive_due_time_is_compared_as_utc():
    scheduler = AccountScheduler()
    account = SimpleNamespace(is_active=True)
    summary = {
        "plan_type": "semi_auto",
        "is_enabled": True,
        "run_strategy": "scheduled",
        "next_run_at": datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1),
    }

    assert scheduler._is_eligible_for_auto_run(account, summary)


@pytest.mark.asyncio
async def test_scheduled_run_uses_shared_task_service_without_overwriting_failure(monkeypatch):
    import app.db.session as session_module
    import app.services.account_service as account_module
    import app.services.task_service as task_module

    account = SimpleNamespace(id="account-1", operation_mode="semi_auto")
    task = SimpleNamespace(id="task-1")
    db = SimpleNamespace(commit=AsyncMock())

    class SessionFactory:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return False

    run_account = AsyncMock(return_value=(account, task))
    run_task = AsyncMock(return_value=None)
    update_status = AsyncMock()
    refresh_next_run = AsyncMock()
    monkeypatch.setattr(session_module, "async_session_factory", SessionFactory)
    monkeypatch.setattr(account_module.account_service, "run_account", run_account)
    monkeypatch.setattr(account_module.account_service, "update_account_run_status", update_status)
    monkeypatch.setattr(account_module.account_service, "refresh_next_run", refresh_next_run)
    monkeypatch.setattr(task_module.task_service, "run_task", run_task)

    await AccountScheduler()._run_account_task(account.id)

    run_account.assert_awaited_once_with(account.id, db, allow_auto=True)
    run_task.assert_awaited_once_with(task.id, db)
    update_status.assert_not_awaited()
    refresh_next_run.assert_not_awaited()
