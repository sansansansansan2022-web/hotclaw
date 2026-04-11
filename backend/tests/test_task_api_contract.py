from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.tables import TaskModel


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
