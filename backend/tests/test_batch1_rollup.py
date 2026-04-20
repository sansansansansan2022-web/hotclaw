from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.post_process_agent import PostProcessAgent
from app.agents.title_generator_agent import TitleGeneratorAgent
from app.services.post_process_service import post_process_service
from app.skills.profile_parse_skill import ProfileParseSkill
from app.skills.registry import skill_registry
from app.skills.title_generate_skill import TitleGenerateSkill


def _llm_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.asyncio
async def test_profile_parse_skill_executes_and_normalizes():
    skill = ProfileParseSkill()

    payload = (
        '{"domain":"technology","subdomain":"ai","target_audience":{"age_range":"25-40","occupation":"builder",'
        '"interests":["ai"]},"tone":"analytical","content_style":"analysis","keywords":["agent"],'
        '"source_preferences":["GitHub","scholar","github"],"research_mode":"enabled","open_source_mode":"enabled"}'
    )

    with patch("app.skills.profile_parse_skill.litellm.acompletion", return_value=_llm_response(payload)):
        result = await skill.execute({"positioning": "Write for AI builders"})

    assert result["status"] == "success"
    assert result["data"]["positioning_raw"] == "Write for AI builders"
    assert result["data"]["source_preferences"] == ["github", "scholar"]


@pytest.mark.asyncio
async def test_title_generate_skill_executes_and_normalizes():
    skill = TitleGenerateSkill()

    payload = (
        '{"selected_topic":"AI agents","titles":['
        '{"title":"AI agents are becoming product infrastructure","style":"direct","score":8.2,"reasoning":"clear"},'
        '{"text":"Why AI agents now belong in the runtime discussion","style":"insight","score":7.9,"reasoning":"fit"}'
        ']}'
    )

    with patch("app.skills.title_generate_skill.litellm.acompletion", return_value=_llm_response(payload)):
        result = await skill.execute(
            {
                "profile": {"positioning_raw": "AI builders"},
                "topics": {"topics": [{"title": "AI agents", "estimated_appeal": 0.9}]},
                "account_context": {"account_name": "HotClaw"},
            }
        )

    assert result["status"] == "success"
    assert result["data"]["selected_topic"] == "AI agents"
    assert len(result["data"]["titles"]) == 2
    assert result["data"]["titles"][0]["text"]


@pytest.mark.asyncio
async def test_title_generator_agent_wrapper_uses_skill_logic():
    agent = TitleGeneratorAgent()
    payload = (
        '{"selected_topic":"AI agents","titles":['
        '{"text":"AI agents are becoming product infrastructure","style":"direct","score":8.2,"reasoning":"clear"}'
        ']}'
    )

    with patch("app.agents.title_generator_agent.litellm.acompletion", return_value=_llm_response(payload)):
        result = await agent.execute(
            {
                "profile": {"positioning_raw": "AI builders"},
                "topics": {"topics": [{"title": "AI agents", "estimated_appeal": 0.9}]},
                "account_context": {"account_name": "HotClaw"},
            },
            {},
        )

    assert result.is_success
    assert result.data["selected_topic"] == "AI agents"
    assert result.data["titles"][0]["style"] == "direct"


def test_new_batch1_skills_are_registered():
    assert skill_registry.has("profile_parse_skill")
    assert skill_registry.has("title_generate_skill")


def test_post_process_service_matches_agent_contract_shape():
    formatter = PostProcessAgent()
    result = post_process_service.prepare(
        formatter=formatter,
        input_data={
            "draft_quality_gate": {"passed": False},
        },
    )

    assert result["used_post_process"] is False
    assert result["post_process_skipped"] is True
    assert result["skip_reason"] == "draft_quality_gate_blocked"
    assert result["template_options"]
