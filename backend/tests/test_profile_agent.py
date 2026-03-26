"""Tests for profile_agent."""

import pytest
from unittest.mock import AsyncMock, patch

from app.agents.profile_agent import ProfileAgent


class TestProfileAgent:
    """Test cases for ProfileAgent."""

    @pytest.fixture
    def agent(self):
        return ProfileAgent()

    def test_agent_id(self, agent):
        assert agent.agent_id == "profile_agent"
        assert agent.name == "账号定位解析智能体"

    def test_parse_json_clean(self, agent):
        """Test parsing clean JSON without markdown."""
        json_str = '{"domain": "职场成长", "subdomain": "互联网职场"}'
        result = agent._parse_json(json_str)
        assert result == {"domain": "职场成长", "subdomain": "互联网职场"}

    def test_parse_json_with_markdown(self, agent):
        """Test parsing JSON wrapped in markdown code block."""
        json_str = '```json\n{"domain": "职场成长", "subdomain": "互联网职场"}\n```'
        result = agent._parse_json(json_str)
        assert result == {"domain": "职场成长", "subdomain": "互联网职场"}

    def test_parse_json_with_backticks_only(self, agent):
        """Test parsing JSON with backticks but no language tag."""
        json_str = '```\n{"domain": "职场成长"}\n```'
        result = agent._parse_json(json_str)
        assert result == {"domain": "职场成长"}

    def test_parse_json_with_whitespace(self, agent):
        """Test parsing JSON with extra whitespace."""
        json_str = '   ```json\n  {"domain": "职场成长"}  \n```   '
        result = agent._parse_json(json_str)
        assert result == {"domain": "职场成长"}

    @pytest.mark.asyncio
    async def test_execute_success(self, agent):
        """Test successful LLM call."""
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"domain": "测试", "subdomain": "测试", "target_audience": {"age_range": "20-30", "occupation": "学生", "interests": ["学习"]}, "tone": "轻松", "content_style": "故事型", "keywords": ["测试"]}'))]

        with patch("app.agents.profile_agent.litellm.acompletion", return_value=mock_response):
            result = await agent.execute(
                {"positioning": "做一个大学生学习账号"},
                {"system_prompt": agent.default_system_prompt}
            )

            assert result.is_success
            assert result.data["domain"] == "测试"
            assert result.data["positioning_raw"] == "做一个大学生学习账号"

    @pytest.mark.asyncio
    async def test_execute_with_fallback_system_prompt(self, agent):
        """Test execute uses context system_prompt, falls back to default."""
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"domain": "测试", "subdomain": "测试", "target_audience": {"age_range": "20-30", "occupation": "学生", "interests": ["学习"]}, "tone": "轻松", "content_style": "故事型", "keywords": ["测试"]}'))]

        with patch("app.agents.profile_agent.litellm.acompletion", return_value=mock_response) as mock_llm:
            await agent.execute(
                {"positioning": "测试"},
                {}  # no system_prompt in context
            )
            # Should use default_system_prompt
            mock_llm.assert_called_once()
            call_args = mock_llm.call_args
            assert call_args.kwargs["messages"][0]["content"] == agent.default_system_prompt

    @pytest.mark.asyncio
    async def test_execute_with_custom_system_prompt(self, agent):
        """Test execute uses custom system_prompt from context."""
        custom_prompt = "自定义提示词"
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content='{"domain": "测试", "subdomain": "测试", "target_audience": {"age_range": "20-30", "occupation": "学生", "interests": ["学习"]}, "tone": "轻松", "content_style": "故事型", "keywords": ["测试"]}'))]

        with patch("app.agents.profile_agent.litellm.acompletion", return_value=mock_response) as mock_llm:
            await agent.execute(
                {"positioning": "测试"},
                {"system_prompt": custom_prompt}
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
