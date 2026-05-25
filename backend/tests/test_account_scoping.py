"""Regression tests for account-scoped task and draft queries."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.api import account_routes, draft_routes
from app.models.tables import AccountModel, ArticleDraftModel, TaskModel
from app.services.account_service import account_service


@pytest_asyncio.fixture
async def scoped_accounts(db_session):
    account_a = AccountModel(
        id="acct-scope-a",
        name="Account A",
        positioning="Account A positioning",
        operation_mode="semi_auto",
        is_active=True,
    )
    account_b = AccountModel(
        id="acct-scope-b",
        name="Account B",
        positioning="Account B positioning",
        operation_mode="semi_auto",
        is_active=True,
    )
    db_session.add_all([account_a, account_b])
    await db_session.commit()
    return account_a, account_b


@pytest_asyncio.fixture
async def scoped_runtime_records(db_session, scoped_accounts):
    account_a, account_b = scoped_accounts
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    tasks = [
        TaskModel(
            id="task-scope-a-1",
            account_id=account_a.id,
            workflow_id="default_pipeline",
            status="completed",
            input_data={"positioning": "A1"},
            created_at=base + timedelta(minutes=3),
        ),
        TaskModel(
            id="task-scope-a-2",
            account_id=account_a.id,
            workflow_id="default_pipeline",
            status="pending",
            input_data={"positioning": "A2"},
            created_at=base + timedelta(minutes=2),
        ),
        TaskModel(
            id="task-scope-b-1",
            account_id=account_b.id,
            workflow_id="default_pipeline",
            status="running",
            input_data={"positioning": "B1"},
            created_at=base + timedelta(minutes=1),
        ),
        TaskModel(
            id="task-scope-global",
            account_id=None,
            workflow_id="default_pipeline",
            status="failed",
            input_data={"positioning": "GLOBAL"},
            created_at=base,
        ),
    ]

    drafts = [
        ArticleDraftModel(
            task_id="task-scope-a-1",
            account_id=account_a.id,
            title="Draft A",
            content_markdown="# Draft A",
            word_count=10,
            draft_status="pending_review",
            publish_status="not_published",
            source_type="semi_auto_task",
        ),
        ArticleDraftModel(
            task_id="task-scope-b-1",
            account_id=account_b.id,
            title="Draft B",
            content_markdown="# Draft B",
            word_count=20,
            draft_status="draft",
            publish_status="not_published",
            source_type="semi_auto_task",
        ),
    ]

    db_session.add_all(tasks + drafts)
    await db_session.commit()
    return {
        "account_a": account_a,
        "account_b": account_b,
        "tasks": tasks,
        "drafts": drafts,
    }


@pytest.mark.asyncio
async def test_list_tasks_filters_strictly_by_account_id(client, scoped_runtime_records):
    account_a = scoped_runtime_records["account_a"]

    resp = await client.get("/api/v1/tasks", params={"account_id": account_a.id, "page": 1, "page_size": 20})

    assert resp.status_code == 200
    body = resp.json()["data"]
    task_ids = [item["task_id"] for item in body["tasks"]]
    assert task_ids == ["task-scope-a-1", "task-scope-a-2"]
    assert all(item["account_id"] == account_a.id for item in body["tasks"])
    assert body["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_task_detail_includes_account_ownership_fields(client, scoped_runtime_records):
    resp = await client.get("/api/v1/tasks/task-scope-a-1")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["account_id"] == "acct-scope-a"
    assert body["account_name"] == "Account A"


@pytest.mark.asyncio
async def test_account_detail_recent_tasks_are_scoped_and_sorted(db_session, scoped_runtime_records):
    account_a = scoped_runtime_records["account_a"]

    detail = await account_service.get_account_detail(account_a.id, db_session, recent_limit=5)

    assert [item["task_id"] for item in detail["recent_tasks"]] == ["task-scope-a-1", "task-scope-a-2"]
    assert all(item["task_id"].startswith("task-scope-a") for item in detail["recent_tasks"])


@pytest.mark.asyncio
async def test_list_drafts_filters_strictly_by_account_id(client, scoped_runtime_records):
    account_b = scoped_runtime_records["account_b"]

    resp = await client.get("/api/v1/drafts", params={"account_id": account_b.id, "page": 1, "page_size": 20})

    assert resp.status_code == 200
    body = resp.json()
    draft_titles = [item["title"] for item in body["drafts"]]
    assert draft_titles == ["Draft B"]
    assert all(item["account_id"] == account_b.id for item in body["drafts"])
    assert body["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_account_run_api_creates_account_owned_task_and_schedules_background(client, db_session, monkeypatch):
    account = AccountModel(
        id="acct-run-api",
        name="Account Run",
        positioning="Account run positioning",
        operation_mode="semi_auto",
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()

    scheduled: dict[str, object] = {}

    class DummyTask:
        pass

    def fake_create_task(coro):
        scheduled["coro"] = coro
        scheduled["task"] = DummyTask()
        return scheduled["task"]

    monkeypatch.setattr(account_routes.asyncio, "create_task", fake_create_task)
    account_routes._background_tasks.clear()

    resp = await client.post(f"/api/v1/accounts/{account.id}/run")

    assert resp.status_code == 200
    body = resp.json()
    task_id = body["task_id"]

    task = await db_session.get(TaskModel, task_id)
    assert task is not None
    assert task.account_id == account.id
    assert body["account_id"] == account.id
    assert body["status"] == "pending"
    assert account_routes._background_tasks[task_id] is scheduled["task"]

    coro = scheduled.get("coro")
    if coro is not None:
        coro.close()


@pytest.mark.asyncio
async def test_disable_account_api_commits_update(client, db_session, monkeypatch):
    account = AccountModel(
        id="acct-disable-api",
        name="Disable API",
        positioning="Disable persistence positioning",
        operation_mode="semi_auto",
        is_active=True,
    )
    db_session.add(account)
    await db_session.commit()

    committed = False
    original_commit = db_session.commit

    async def commit_spy():
        nonlocal committed
        committed = True
        await original_commit()

    monkeypatch.setattr(db_session, "commit", commit_spy)

    resp = await client.post(f"/api/v1/accounts/{account.id}/disable")

    assert resp.status_code == 200, resp.text
    assert committed is True
    await db_session.refresh(account)
    assert account.is_active is False


@pytest.mark.asyncio
async def test_draft_rerun_api_creates_guarded_background_task(client, db_session, monkeypatch):
    account = AccountModel(
        id="acct-draft-rerun-api",
        name="Draft Rerun API",
        positioning="Rerun this account through the guarded run path.",
        operation_mode="semi_auto",
        is_active=True,
    )
    original_task = TaskModel(
        id="task-draft-rerun-original",
        account_id=account.id,
        workflow_id="default_pipeline",
        status="completed",
        input_data={"positioning": account.positioning},
    )
    draft = ArticleDraftModel(
        task_id=original_task.id,
        account_id=account.id,
        title="Approved Draft",
        content_markdown="# Approved Draft",
        word_count=20,
        draft_status="approved",
        publish_status="not_published",
        source_type="semi_auto_task",
    )
    db_session.add_all([account, original_task, draft])
    await db_session.commit()

    async def fake_evaluate_account_run(*args, **kwargs):
        return {
            "run_strategy": {
                "allow_run": True,
                "effective_mode": "semi_auto",
                "allow_auto_publish": False,
                "preferred_reference_source_ids": [],
                "avoid_recent_topics": [],
            },
            "ops_notes": [],
            "fallback_used": True,
        }

    monkeypatch.setattr(
        "app.services.account_service.account_harness_service.evaluate_account_run",
        fake_evaluate_account_run,
    )

    scheduled: dict[str, object] = {}

    class DummyTask:
        pass

    def fake_create_task(coro):
        scheduled["coro"] = coro
        scheduled["task"] = DummyTask()
        return scheduled["task"]

    monkeypatch.setattr(draft_routes.asyncio, "create_task", fake_create_task)
    draft_routes._background_tasks.clear()

    resp = await client.post(f"/api/v1/drafts/{draft.id}/rerun")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    new_task = await db_session.get(TaskModel, body["new_task_id"])
    assert new_task is not None
    assert new_task.account_id == account.id
    assert isinstance(new_task.input_data.get("ops_context"), dict)
    assert draft_routes._background_tasks[new_task.id] is scheduled["task"]

    coro = scheduled.get("coro")
    if coro is not None:
        coro.close()
    draft_routes._background_tasks.clear()
