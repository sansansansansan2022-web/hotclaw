"""TaskService.run_task critical state management tests."""

import asyncio
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import HotClawError
from app.models.tables import AccountModel, TaskModel
from app.services.task_service import task_service


@pytest.mark.asyncio
async def test_run_task_rejects_non_pending_task(db_session):
    """Only pending tasks can be executed."""
    task = TaskModel(
        id="task-non-pending",
        workflow_id="default_pipeline",
        status="completed",
        input_data={"positioning": "x"},
    )
    db_session.add(task)
    await db_session.commit()

    with pytest.raises(HotClawError) as exc:
        await task_service.run_task(task.id, db_session)

    assert exc.value.code == 2003


@pytest.mark.asyncio
async def test_run_task_updates_account_status_and_next_run_on_success(db_session, monkeypatch):
    """Success path should persist account.last_run_status=success and refreshed next_run_at."""
    account = AccountModel(
        id="acc-success",
        name="A",
        positioning="P",
        operation_mode="semi_auto",
        auto_run_enabled=True,
        is_active=True,
        posting_frequency="daily",
        next_run_at=datetime.now(timezone.utc) - timedelta(hours=1),
        last_run_status="running",
    )
    task = TaskModel(
        id="task-success",
        workflow_id="default_pipeline",
        status="pending",
        input_data={"positioning": "x"},
        account_id=account.id,
    )
    db_session.add_all([account, task])
    await db_session.commit()

    async def _fake_run(task_obj, db):
        now = datetime.now(timezone.utc)
        task_obj.status = "completed"
        task_obj.started_at = now - timedelta(seconds=2)
        task_obj.completed_at = now
        task_obj.result_data = {"content": "ok"}
        db.add(task_obj)
        await db.flush()
        return {"content": "ok"}

    async def _skip_draft(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.task_service.orchestrator_engine.run", _fake_run)
    monkeypatch.setattr(task_service, "_create_draft_from_task_result", _skip_draft)

    await task_service.run_task(task.id, db_session)

    refreshed = await db_session.execute(select(AccountModel).where(AccountModel.id == account.id))
    saved_account = refreshed.scalar_one()
    assert saved_account.last_run_status == "success"
    assert saved_account.next_run_at is not None
    assert saved_account.next_run_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_run_task_updates_account_status_on_failure(db_session, monkeypatch):
    """Failure path should persist account.last_run_status=failed."""
    account = AccountModel(
        id="acc-failed",
        name="A",
        positioning="P",
        operation_mode="semi_auto",
        auto_run_enabled=True,
        is_active=True,
        posting_frequency="daily",
        last_run_status="running",
    )
    task = TaskModel(
        id="task-failed",
        workflow_id="default_pipeline",
        status="pending",
        input_data={"positioning": "x"},
        account_id=account.id,
    )
    db_session.add_all([account, task])
    await db_session.commit()

    async def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.task_service.orchestrator_engine.run", _boom)

    await task_service.run_task(task.id, db_session)

    refreshed = await db_session.execute(select(AccountModel).where(AccountModel.id == account.id))
    saved_account = refreshed.scalar_one()
    assert saved_account.last_run_status == "failed"
    assert saved_account.last_error_message == "boom"


@pytest.mark.asyncio
async def test_run_task_marks_timeout_with_terminal_state(db_session, monkeypatch):
    """Timeout path should record a terminal failed state with execution metadata."""
    account = AccountModel(
        id="acc-timeout",
        name="A",
        positioning="P",
        operation_mode="semi_auto",
        auto_run_enabled=True,
        is_active=True,
        posting_frequency="daily",
        last_run_status="running",
    )
    task = TaskModel(
        id="task-timeout",
        workflow_id="default_pipeline",
        status="pending",
        input_data={"positioning": "x"},
        account_id=account.id,
    )
    db_session.add_all([account, task])
    await db_session.commit()

    async def _slow_run(*args, **kwargs):
        await asyncio.sleep(0.05)
        return {"content": "never reached"}

    monkeypatch.setattr("app.services.task_service.orchestrator_engine.run", _slow_run)
    monkeypatch.setattr(task_service, "_get_task_timeout_seconds", lambda: 0.01)

    await task_service.run_task(task.id, db_session)

    refreshed_task = await db_session.get(TaskModel, task.id)
    refreshed_account = await db_session.get(AccountModel, account.id)

    assert refreshed_task is not None
    assert refreshed_task.status == "failed"
    assert refreshed_task.completed_at is not None
    assert "timed out" in (refreshed_task.error_message or "")
    assert isinstance(refreshed_task.result_data, dict)
    assert refreshed_task.result_data["execution_meta"]["timed_out"] is True
    assert refreshed_account is not None
    assert refreshed_account.last_run_status == "failed"
