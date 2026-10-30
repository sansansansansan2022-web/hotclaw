from app.agents.registry import agent_registry
from app.orchestrator.engine import DEFAULT_WORKFLOW_NODES, OrchestratorEngine
from app.orchestrator.workspace import Workspace
import pytest
from types import SimpleNamespace


def test_account_operations_uses_manager_and_five_specialists():
    registered = {agent.agent_id for agent in agent_registry.list_all()}
    assert registered == {
        "account_ops_agent", "profile_agent", "hot_topic_agent",
        "topic_planner_agent", "content_writer_agent", "audit_agent",
    }
    nodes = {node["node_id"]: node for node in DEFAULT_WORKFLOW_NODES}
    assert nodes["rewrite_agent"]["agent_id"] == "content_writer_agent"
    assert nodes["audit_revision"]["agent_id"] == "audit_agent"
    assert nodes["post_process_agent"]["executor"] == "service"


def test_writer_revision_only_follows_failed_audit():
    engine = OrchestratorEngine()
    workspace = Workspace(task_id="test", input_data={})
    workspace.set("audit_result", {"passed": True, "risk_level": "medium"})
    assert not engine._should_run_rewrite(workspace)
    workspace.set("audit_result", {"passed": False, "risk_level": "medium"})
    assert engine._should_run_rewrite(workspace)


@pytest.mark.asyncio
async def test_research_uses_live_news_when_rss_skill_is_empty(monkeypatch):
    from app.services.hot_topic_analysis_service import hot_topic_analysis_service
    from app.services.news_source_service import news_source_service

    async def fake_collect(*, snapshot, query_plan):
        assert query_plan["selected_topic"] == "agent observability"
        return [{
            "title": "New agent tracing release",
            "source_name": "Example News",
            "source_url": "https://example.org/news",
            "summary": "Recent tracing release",
            "relevance_score": 0.8,
        }], []

    monkeypatch.setattr(news_source_service, "collect_candidates", fake_collect)
    results = await hot_topic_analysis_service._fetch_news_fallback(
        profile={}, account_context={}, query_plan={"selected_topic": "agent observability"},
    )
    assert results[0]["title"] == "New agent tracing release"
    assert results[0]["url"] == "https://example.org/news"


@pytest.mark.asyncio
async def test_writer_revision_receives_audit_findings(monkeypatch):
    from app.agents.content_writer_agent import ContentWriterAgent

    writer = ContentWriterAgent()
    captured = {}

    async def fake_completion(**kwargs):
        captured["prompt"] = kwargs["messages"][1]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"revised_content_markdown":"Revised article","used_rewrite":true}'
        ))])

    monkeypatch.setattr(writer, "run_litellm_completion", fake_completion)
    result = await writer.execute({
        "content": {"content_markdown": "Original article"},
        "audit_result": {"passed": False, "issues": [{"message": "Fix the opening"}]},
    }, {})
    assert result.is_success
    assert result.data["revised_content_markdown"] == "Revised article"
    assert "Fix the opening" in captured["prompt"]
