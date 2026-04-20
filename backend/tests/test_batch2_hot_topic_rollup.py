from __future__ import annotations

from time import monotonic

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.hot_topic_agent import HotTopicAgent
from app.services.hot_topic_analysis_service import hot_topic_analysis_service


@pytest.mark.asyncio
async def test_hot_topic_agent_wrapper_delegates_to_service(monkeypatch):
    async def _fake_execute(*, agent, input_data, context):
        assert isinstance(agent, HotTopicAgent)
        assert input_data["profile"]["positioning_raw"] == "AI tooling account"
        assert context["task_id"] == "task_batch2"
        return agent._success({"hot_topics": [{"title": "Topic A"}]})

    monkeypatch.setattr(hot_topic_analysis_service, "execute", _fake_execute)

    result = await HotTopicAgent().execute(
        {"profile": {"positioning_raw": "AI tooling account"}},
        {"task_id": "task_batch2"},
    )

    assert result.is_success
    assert result.data["hot_topics"][0]["title"] == "Topic A"


@pytest.mark.asyncio
async def test_hot_topic_analysis_service_collects_and_dedupes_external_evidence(monkeypatch):
    monkeypatch.setattr(
        "app.services.hot_topic_analysis_service.skill_router_service.plan_invocations",
        lambda **kwargs: [
            {"skill_name": "github_project_curator_skill", "input_data": {"topic": "agent runtime"}},
            {"skill_name": "scholar_paper_search_skill", "input_data": {"topic": "agent runtime"}},
        ],
    )

    async def _fake_invoke(*, skill_name, **kwargs):
        shared = {
            "id": "shared-item",
            "source_id": "shared-item",
            "title": "Shared evidence",
            "summary": "Shared summary",
            "source_type": "github_repo" if skill_name == "github_project_curator_skill" else "scholar_paper",
        }
        return {
            "workspace_payload": {
                "fetched_evidence": [shared],
                "selected_evidence": [shared],
                "evidence_summaries": {skill_name: f"{skill_name} summary"},
                "citation_guardrails": {"must_ground_titles_in_evidence": True},
            }
        }

    monkeypatch.setattr(
        "app.services.hot_topic_analysis_service.skill_runtime_service.invoke",
        _fake_invoke,
    )

    payload = await hot_topic_analysis_service._collect_external_evidence(
        profile={"positioning_raw": "AI tooling account"},
        account_context={"positioning": "AI tooling"},
        query_plan={"selected_topic": "agent runtime"},
        context={
            "db": object.__new__(AsyncSession),
            "task_id": "task_batch2",
            "account_id": "acct_batch2",
        },
        started_at=monotonic(),
        node_timeout_seconds=300,
    )

    assert len(payload["fetched_evidence"]) == 1
    assert len(payload["selected_evidence"]) == 1
    assert payload["selected_evidence"][0]["title"] == "Shared evidence"
    assert set(payload["evidence_summaries"].keys()) == {
        "github_project_curator_skill",
        "scholar_paper_search_skill",
    }


@pytest.mark.asyncio
async def test_hot_topic_analysis_service_fallback_keeps_contract_without_sources():
    result = await hot_topic_analysis_service.fallback(
        agent=HotTopicAgent(),
        error=RuntimeError("timeout"),
        input_data={
            "profile": {"positioning_raw": "面向 AI 工程师做工具和工作流解读"},
            "account_context": {"positioning": "AI 工具拆解", "audience": "AI 工程师"},
            "ops_context": {},
        },
    )

    assert result is not None
    assert result.is_success
    assert result.data["hot_topics"]
    assert result.data["hot_topics"][0]["source"] == "account_positioning_fallback"
    assert "reference_digest" in result.data
