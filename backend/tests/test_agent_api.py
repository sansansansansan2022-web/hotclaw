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
    agent_ids = [a["agent_id"] for a in agents]
    assert "profile_agent" in agent_ids
    assert "editorial_review_agent" in agent_ids
    assert "topic_selection_agent" in agent_ids
    assert "content_drafter_agent" in agent_ids
    assert "memory_curator_agent" in agent_ids
    # merged agents no longer registered
    assert "audit_agent" not in agent_ids
    assert "style_reviewer_agent" not in agent_ids
    assert "structure_reviewer_agent" not in agent_ids
    assert "topic_planner_agent" not in agent_ids
    assert "title_generator_agent" not in agent_ids
    assert "outline_planner_agent" not in agent_ids
    assert "section_writer_agent" not in agent_ids


@pytest.mark.asyncio
async def test_get_agent_not_found(client: AsyncClient):
    """Error case: get a non-existent agent."""
    resp = await client.get("/api/v1/agents/nonexistent_agent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 1003
