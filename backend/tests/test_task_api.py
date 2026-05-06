"""Tests for task API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_task_success(client: AsyncClient):
    """Normal case: create a task with valid positioning."""
    resp = await client.post("/api/v1/tasks", json={
        "positioning": "我是一个关注职场成长的公众号，目标读者是25-35岁互联网从业者",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["task_id"] is not None
    assert body["data"]["status"] == "pending"
    assert body["data"]["workflow_id"] == "default_pipeline"


@pytest.mark.asyncio
async def test_create_task_validation_error(client: AsyncClient):
    """Error case: positioning too short (min_length=5)."""
    resp = await client.post("/api/v1/tasks", json={
        "positioning": "hi",
    })
    assert resp.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_get_task_not_found(client: AsyncClient):
    """Error case: query a non-existent task."""
    resp = await client.get("/api/v1/tasks/nonexistent_task_id")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 1002


@pytest.mark.asyncio
async def test_list_tasks_empty(client: AsyncClient):
    """Normal case: list tasks when there are none."""
    resp = await client.get("/api/v1/tasks?page=1&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["tasks"] == []
    assert body["data"]["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Normal case: health check endpoint."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
