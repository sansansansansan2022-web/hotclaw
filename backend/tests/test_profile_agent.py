"""Tests for profile_agent."""

import json

import pytest
from unittest.mock import AsyncMock

from app.agents.profile_agent import ProfileAgent
from app.llm.base import LLMResponse
from app.llm.gateway import LLMGateway


_PARSED = {
    "domain": "测试",
    "subdomain": "测试",
    "target_audience": {
        "age_range": "20-30",
        "occupation": "学生",
        "interests": ["学习"],
    },
    "tone": "轻松",
    "content_style": "故事型",
    "keywords": ["测试"],
}


def _profile_llm_response() -> LLMResponse:
    return LLMResponse(
        content=json.dumps(_PARSED, ensure_ascii=False),
        model="mock-model",
        provider="mock",
        parsed=dict(_PARSED),
    )


class TestProfileAgent:
    """Test cases for ProfileAgent."""

    @pytest.fixture
    def agent(self):
        return ProfileAgent()

    def test_agent_id(self, agent):
        assert agent.agent_id == "profile_agent"
        assert agent.name == "账号定位解析智能体"

    def test_parse_json_clean(self):
        """JSON parsing is owned by LLMGateway; agent delegates to response.parsed."""
        json_str = '{"domain": "职场成长", "subdomain": "互联网职场"}'
        result = LLMGateway._parse_json(json_str)
        assert result == {"domain": "职场成长", "subdomain": "互联网职场"}

    def test_parse_json_with_markdown(self):
        json_str = '```json\n{"domain": "职场成长", "subdomain": "互联网职场"}\n```'
        result = LLMGateway._parse_json(json_str)
        assert result == {"domain": "职场成长", "subdomain": "互联网职场"}

    def test_parse_json_with_backticks_only(self):
        json_str = '```\n{"domain": "职场成长"}\n```'
        result = LLMGateway._parse_json(json_str)
        assert result == {"domain": "职场成长"}

    def test_parse_json_with_whitespace(self):
        json_str = '   ```json\n  {"domain": "职场成长"}  \n```   '
        result = LLMGateway._parse_json(json_str)
        assert result == {"domain": "职场成长"}

    @pytest.mark.asyncio
    async def test_execute_success(self, agent, monkeypatch):
        """Test successful LLM call via llm_gateway."""

        async def _complete(**kwargs):
            return _profile_llm_response()

        monkeypatch.setattr("app.agents.profile_agent.llm_gateway.complete", _complete)
        result = await agent.execute(
            {"positioning": "做一个大学生学习账号"},
            {"system_prompt": agent.default_system_prompt},
        )

        assert result.is_success
        assert result.data["domain"] == "测试"
        assert result.data["positioning_raw"] == "做一个大学生学习账号"

    @pytest.mark.asyncio
    async def test_execute_with_fallback_system_prompt(self, agent, monkeypatch):
        """Test execute uses context system_prompt, falls back to default."""
        mock_llm = AsyncMock(return_value=_profile_llm_response())
        monkeypatch.setattr("app.agents.profile_agent.llm_gateway.complete", mock_llm)
        await agent.execute(
            {"positioning": "测试"},
            {},  # no system_prompt in context
        )
        mock_llm.assert_called_once()
        call_args = mock_llm.call_args
        assert call_args.kwargs["messages"][0]["content"] == agent.default_system_prompt

    @pytest.mark.asyncio
    async def test_execute_with_custom_system_prompt(self, agent, monkeypatch):
        """Test execute uses custom system_prompt from context."""
        custom_prompt = "自定义提示词"
        mock_llm = AsyncMock(return_value=_profile_llm_response())
        monkeypatch.setattr("app.agents.profile_agent.llm_gateway.complete", mock_llm)
        await agent.execute(
            {"positioning": "测试"},
            {"system_prompt": custom_prompt},
        )
        mock_llm.assert_called_once()
        call_args = mock_llm.call_args
        assert call_args.kwargs["messages"][0]["content"] == custom_prompt

    @pytest.mark.asyncio
    async def test_fallback(self, agent):
        """Test fallback returns default profile."""
        result = await agent.fallback(Exception("test error"), {"positioning": "测试"})
        assert result is not None
        assert result.is_success
        assert result.data["domain"] == "泛资讯"
        assert result.data["positioning_raw"] == "测试"
