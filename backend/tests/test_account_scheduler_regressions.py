"""Regression tests for critical scheduler/account state bugs."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.tables import AccountModel, TaskModel
from app.scheduler.account_scheduler import AccountScheduler, account_scheduler


def test_final_eligibility_accepts_naive_due_timestamp():
    """Persisted naive datetimes should not crash the scheduler's final guard."""
    scheduler = AccountScheduler()
    account = SimpleNamespace(
        is_active=True,
        auto_run_enabled=True,
        operation_mode="semi_auto",
        next_run_at=datetime.now() - timedelta(minutes=5),
    )

    assert scheduler._is_eligible_for_auto_run(account) is True


@pytest.mark.asyncio
async def test_scheduler_preserves_failed_task_status(db_session, monkeypatch):
    """Scheduler must not mark an account successful after TaskService records failure."""
    error_message = "scheduler orchestrator boom"
    account = AccountModel(
        id="scheduler-failed-account",
        name="Scheduler Failed Account",
        positioning="Scheduler failure positioning",
        operation_mode="semi_auto",
        auto_run_enabled=True,
        is_active=True,
        posting_frequency="daily",
        next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        last_run_status="never_run",
    )
    db_session.add(account)
    await db_session.commit()

    async def _boom(*args, **kwargs):
        raise RuntimeError(error_message)

    class _SessionContext:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("app.db.session.async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr("app.services.task_service.orchestrator_engine.run", _boom)

    await account_scheduler._run_account_task(account.id)

    await db_session.refresh(account)
    task_result = await db_session.execute(
        select(TaskModel).where(TaskModel.account_id == account.id)
    )
    saved_task = task_result.scalar_one()

    assert saved_task.status == "failed"
    assert saved_task.error_message == error_message
    assert account.last_run_status == "failed"
    assert account.last_error_message == error_message
