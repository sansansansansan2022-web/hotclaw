from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agents.rewrite_agent import RewriteAgent
from app.agents.outline_planner_agent import OutlinePlannerAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.profile_agent import ProfileAgent
from app.agents.section_writer_agent import SectionWriterAgent


def _fake_llm_response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False)))]
    )


@pytest.mark.asyncio
async def test_outline_planner_uses_node_timeout_budget(monkeypatch):
    observed: dict[str, object] = {}

    async def _fake_completion(**kwargs):
        observed.update(kwargs)
        return _fake_llm_response(
            {
                "article_goal": "Explain why AI agent runtime costs now shape product decisions.",
                "why_this_topic": "AI agent runtime costs are now visible to builders.",
                "strategic_angle": "Connect AI agent runtime costs to product architecture.",
                "opening_hook": "AI agent runtime costs stop being invisible once products scale.",
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "AI agent runtime costs are a product constraint",
                        "purpose": "Keep the outline locked to AI agent runtime costs.",
                        "summary": "AI agent runtime costs affect product design.",
                        "key_points": ["AI agent runtime costs influence workflows."],
                    }
                ],
                "ending_cta": "Use AI agent runtime costs as a design input.",
                "summary": "AI agent runtime costs deserve explicit planning.",
            }
        )

    monkeypatch.setattr("app.agents.outline_planner_agent.litellm.acompletion", _fake_completion)

    result = await OutlinePlannerAgent().execute(
        {
            "profile": {"positioning_raw": "Developer tooling account."},
            "topics": {"selected_topic": "AI agent runtime costs"},
            "titles": {"selected_title": "AI agent runtime costs are now a product question"},
        },
        {"node_timeout_seconds": 300},
    )

    assert result.is_success
    assert float(observed["timeout"]) >= 290


@pytest.mark.asyncio
async def test_outline_planner_retries_transient_connection_errors(monkeypatch):
    observed = {"calls": 0}

    async def _fake_completion(**kwargs):
        observed["calls"] += 1
        if observed["calls"] == 1:
            raise RuntimeError(
                "litellm.InternalServerError: InternalServerError: DashscopeException - Connection error."
            )
        return _fake_llm_response(
            {
                "article_goal": "Explain why AI agent runtime costs now shape product decisions.",
                "why_this_topic": "AI agent runtime costs are now visible to builders.",
                "strategic_angle": "Connect AI agent runtime costs to product architecture.",
                "opening_hook": "AI agent runtime costs stop being invisible once products scale.",
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "AI agent runtime costs are a product constraint",
                        "purpose": "Keep the outline locked to AI agent runtime costs.",
                        "summary": "AI agent runtime costs affect product design.",
                        "key_points": ["AI agent runtime costs influence workflows."],
                    }
                ],
                "ending_cta": "Use AI agent runtime costs as a design input.",
                "summary": "AI agent runtime costs deserve explicit planning.",
            }
        )

    monkeypatch.setattr("app.agents.outline_planner_agent.litellm.acompletion", _fake_completion)

    result = await OutlinePlannerAgent().execute(
        {
            "profile": {"positioning_raw": "Developer tooling account."},
            "topics": {"selected_topic": "AI agent runtime costs"},
            "titles": {"selected_title": "AI agent runtime costs are now a product question"},
        },
        {"node_timeout_seconds": 300},
    )

    assert result.is_success
    assert observed["calls"] == 2
    assert result.runtime_trace is not None
    assert result.runtime_trace["retry_count"] == 1
    assert result.runtime_trace["error_class"] is None


@pytest.mark.asyncio
async def test_outline_planner_falls_back_after_persistent_connection_errors(monkeypatch):
    async def _fake_completion(**kwargs):
        raise RuntimeError(
            "litellm.InternalServerError: InternalServerError: DashscopeException - Connection error."
        )

    monkeypatch.setattr("app.agents.outline_planner_agent.litellm.acompletion", _fake_completion)

    result = await OutlinePlannerAgent().execute(
        {
            "profile": {"positioning_raw": "Developer tooling account."},
            "topics": {"selected_topic": "AI agent runtime costs"},
            "titles": {"selected_title": "AI agent runtime costs are now a product question"},
        },
        {"node_timeout_seconds": 300},
    )

    assert result.is_success
    assert result.data["sections"]
    assert result.data["summary"] == "Structured outline fallback for AI agent runtime costs are now a product question."


@pytest.mark.asyncio
async def test_section_writer_uses_node_timeout_budget(monkeypatch):
    observed: dict[str, object] = {}

    async def _fake_completion(**kwargs):
        observed.update(kwargs)
        return _fake_llm_response(
            {
                "section_drafts": [
                    {
                        "section_id": "s1",
                        "heading": "AI agent runtime costs are a product constraint",
                        "summary": "AI agent runtime costs affect product design.",
                        "content_markdown": "AI agent runtime costs change how teams price, route, and monitor agent workflows.",
                    }
                ]
            }
        )

    monkeypatch.setattr("app.agents.section_writer_agent.litellm.acompletion", _fake_completion)

    result = await SectionWriterAgent().execute(
        {
            "topics": {"selected_topic": "AI agent runtime costs"},
            "titles": {"selected_title": "AI agent runtime costs are now a product question"},
            "outline_plan": {
                "sections": [
                    {
                        "section_id": "s1",
                        "heading": "AI agent runtime costs are a product constraint",
                        "summary": "AI agent runtime costs affect product design.",
                    }
                ]
            },
        },
        {"node_timeout_seconds": 300},
    )

    assert result.is_success
    assert float(observed["timeout"]) >= 290


@pytest.mark.asyncio
async def test_content_writer_uses_node_timeout_budget(monkeypatch):
    observed: dict[str, object] = {}

    async def _fake_completion(**kwargs):
        observed.update(kwargs)
        return _fake_llm_response(
            {
                "content_markdown": "# Runtime costs\n\nAI agent runtime costs shape product decisions.",
                "word_count": 9,
                "structure": {"sections": [{"heading": "Runtime costs", "summary": "Product pressure"}]},
                "tags": ["ai agents"],
            }
        )

    monkeypatch.setattr("app.agents.content_writer_agent.litellm.acompletion", _fake_completion)

    result = await ContentWriterAgent().execute(
        {
            "profile": {"domain": "technology", "tone": "analytical"},
            "topics": {"topics": [{"title": "AI agent runtime costs", "estimated_appeal": 0.9}]},
            "titles": {"titles": [{"text": "AI agent runtime costs are now a product question"}]},
            "hot_topics": {"hot_topics": [{"title": "AI agent runtime costs"}]},
        },
        {"node_timeout_seconds": 300},
    )

    assert result.is_success
    assert float(observed["timeout"]) >= 290


@pytest.mark.asyncio
async def test_rewrite_agent_uses_node_timeout_budget(monkeypatch):
    observed: dict[str, object] = {}

    async def _fake_completion(**kwargs):
        observed.update(kwargs)
        return _fake_llm_response(
            {
                "revised_content_markdown": "# Runtime costs\n\nRewrite completed.",
                "revision_summary": "Tightened the article around the main argument.",
                "fixed_issues": ["generic_style"],
                "changed_sections": ["s1"],
                "used_rewrite": True,
            }
        )

    monkeypatch.setattr("app.agents.rewrite_agent.litellm.acompletion", _fake_completion)

    result = await RewriteAgent().execute(
        {
            "assembled_article": {
                "selected_title": "AI agent runtime costs are now a product question",
                "selected_topic": "AI agent runtime costs",
                "summary": "Runtime costs are now visible to product builders.",
                "content_markdown": "# Draft\n\nOriginal content.",
            },
            "style_review": {"issues": [{"severity": "medium", "code": "generic_style"}]},
            "structure_review": {"issues": []},
            "review_results": [],
            "outline_plan": {
                "sections": [
                    {"section_id": "s1", "heading": "Why it matters", "summary": "Frame the shift."}
                ]
            },
            "section_drafts": {"section_drafts": [{"section_id": "s1", "content_markdown": "Original content."}]},
        },
        {"node_timeout_seconds": 600},
    )

    assert result.is_success
    assert float(observed["timeout"]) >= 590


@pytest.mark.asyncio
async def test_profile_agent_uses_per_agent_model_config(monkeypatch):
    observed: dict[str, object] = {}

    async def _fake_completion(**kwargs):
        observed.update(kwargs)
        return _fake_llm_response(
            {
                "domain": "technology",
                "target_audience": "AI builders",
                "tone": "analytical",
                "content_lane": "analysis",
                "source_preferences": ["papers"],
            }
        )

    monkeypatch.setattr("app.agents.profile_agent.litellm.acompletion", _fake_completion)

    result = await ProfileAgent().execute(
        {"positioning": "Write for AI builders."},
        {
            "agent_model_config": {
                "provider_id": "openai",
                "model": "gpt-4.1-mini",
                "api_key": "test-key",
                "base_url": "https://api.openai.com/v1",
            }
        },
    )

    assert result.is_success
    assert observed["custom_llm_provider"] == "openai"
    assert observed["model"] == "gpt-4.1-mini"
    assert observed["api_key"] == "test-key"
    assert observed["base_url"] == "https://api.openai.com/v1"
    assert result.runtime_trace is not None
    assert result.runtime_trace["provider"] == "openai"
    assert result.runtime_trace["model"] == "gpt-4.1-mini"
