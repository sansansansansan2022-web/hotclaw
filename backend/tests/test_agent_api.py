"""Tests for agent API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_agents_success(client: AsyncClient):
    """Normal case: list all registered agents."""
    resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    agents = body["data"]["agents"]
    assert len(agents) == 6  # 6 mock agents registered
    agent_ids = [a["agent_id"] for a in agents]
    assert "profile_agent" in agent_ids
    assert "audit_agent" in agent_ids


@pytest.mark.asyncio
async def test_get_agent_not_found(client: AsyncClient):
    """Error case: get a non-existent agent."""
    resp = await client.get("/api/v1/agents/nonexistent_agent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 1003
