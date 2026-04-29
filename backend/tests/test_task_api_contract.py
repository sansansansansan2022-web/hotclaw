from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.tables import ArticleDraftModel, TaskModel


@pytest.mark.asyncio
async def test_get_task_status_accepts_naive_started_at(client, db_session):
    task = TaskModel(
        id="task-naive-started-at",
        workflow_id="default_pipeline",
        status="running",
        input_data={"positioning": "contract"},
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db_session.add(task)
    await db_session.commit()

    response = await client.get(f"/api/v1/tasks/{task.id}/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["status"] == "running"
    assert payload["data"]["started_at"].endswith("+00:00")
    assert payload["data"]["elapsed_seconds"] is not None


@pytest.mark.asyncio
async def test_delete_task_removes_task_and_related_drafts(client, db_session):
    task = TaskModel(
        id="task-delete-contract",
        workflow_id="default_pipeline",
        status="pending",
        input_data={"positioning": "contract"},
    )
    db_session.add(task)
    db_session.add(
        ArticleDraftModel(
            task_id=task.id,
            title="Delete me",
            content_markdown="content",
            draft_status="draft",
            publish_status="not_published",
            source_type="manual_task",
        )
    )
    await db_session.commit()

    response = await client.delete(f"/api/v1/tasks/{task.id}")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["task_id"] == task.id
    assert payload["data"]["deleted"] is True
    assert payload["data"]["previous_status"] == "pending"
    assert payload["data"]["stopped_before_delete"] is True

    task_result = await db_session.execute(select(TaskModel).where(TaskModel.id == task.id))
    assert task_result.scalar_one_or_none() is None
    draft_result = await db_session.execute(select(ArticleDraftModel).where(ArticleDraftModel.task_id == task.id))
    assert draft_result.scalar_one_or_none() is None
