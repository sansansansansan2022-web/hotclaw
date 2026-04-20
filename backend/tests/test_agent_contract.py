"""Tests for Agent Contract and Skill system.

【Agent Contract 与 Skill 测试】
验证：
1. 6 个基础 Agent 的 input_schema / output_schema 存在
2. hot_topic_fetch_skill 执行成功时输出结构正确
3. skill_registry 能发现 hot_topic_fetch_skill
4. Agent 的 get_contract() 返回完整契约
5. Skill 的 get_contract() 返回完整契约
"""

import pytest
from unittest.mock import patch, AsyncMock

from app.agents.profile_agent import ProfileAgent
from app.agents.hot_topic_agent import HotTopicAgent
from app.agents.topic_planner_agent import TopicPlannerAgent
from app.agents.title_generator_agent import TitleGeneratorAgent
from app.agents.content_writer_agent import ContentWriterAgent
from app.agents.audit_agent import AuditAgent
from app.skills.hot_topic_fetch_skill import HotTopicFetchSkill
from app.skills.registry import skill_registry


# =============================================================================
# Test 1: 6 个 Agent 都有 Contract
# =============================================================================

class TestAgentContracts:
    """Test that all 6 agents have valid contracts."""

    @pytest.mark.parametrize("agent_class,expected_id,expected_skills", [
        (ProfileAgent, "profile_agent", ["profile_parse_skill"]),
        (HotTopicAgent, "hot_topic_agent", ["hot_topic_fetch_skill"]),
        (TopicPlannerAgent, "topic_planner_agent", []),
        (TitleGeneratorAgent, "title_generator_agent", ["title_generate_skill"]),
        (ContentWriterAgent, "content_writer_agent", []),
        (AuditAgent, "audit_agent", []),
    ])
    def test_agent_has_contract(self, agent_class, expected_id, expected_skills):
        """Test that each agent has valid input/output schema."""
        agent = agent_class()

        # Basic identity
        assert agent.agent_id == expected_id, f"Expected id {expected_id}"
        assert agent.name, "Agent should have a name"
        assert agent.description, "Agent should have a description"

        # Contract schemas
        assert agent.input_schema, f"{expected_id} should have input_schema"
        assert agent.output_schema, f"{expected_id} should have output_schema"
        assert isinstance(agent.input_schema, dict), "input_schema should be dict"
        assert isinstance(agent.output_schema, dict), "output_schema should be dict"

        # Supported skills
        assert agent.supported_skills == expected_skills, \
            f"{expected_id} supported_skills should be {expected_skills}"

    def test_hot_topic_agent_supports_skill(self):
        """Test that HotTopicAgent declares it supports hot_topic_fetch_skill."""
        agent = HotTopicAgent()
        assert "hot_topic_fetch_skill" in agent.supported_skills

    def test_agent_get_contract(self):
        """Test that agent.get_contract() returns complete contract."""
        agent = ProfileAgent()
        contract = agent.get_contract()

        assert "agent_id" in contract
        assert "name" in contract
        assert "description" in contract
        assert "input_schema" in contract
        assert "output_schema" in contract
        assert "supported_skills" in contract


# =============================================================================
# Test 2: hot_topic_fetch_skill 结构验证
# =============================================================================

class TestHotTopicFetchSkill:
    """Test hot_topic_fetch_skill contract and structure."""

    def test_skill_has_contract(self):
        """Test that skill has valid input/output schema."""
        skill = HotTopicFetchSkill()

        assert skill.skill_id == "hot_topic_fetch_skill"
        assert skill.name, "Skill should have a name"
        assert skill.description, "Skill should have a description"
        assert skill.input_schema, "Skill should have input_schema"
        assert skill.output_schema, "Skill should have output_schema"

    def test_skill_get_contract(self):
        """Test that skill.get_contract() returns complete contract."""
        skill = HotTopicFetchSkill()
        contract = skill.get_contract()

        assert contract["skill_id"] == "hot_topic_fetch_skill"
        assert "input_schema" in contract
        assert "output_schema" in contract

    def test_skill_schema_structure(self):
        """Test skill input/output schema structure."""
        skill = HotTopicFetchSkill()

        # Input schema should describe keywords
        assert "keywords" in skill.input_schema.get("properties", {})

        # Output schema should describe results
        assert "results" in skill.output_schema.get("properties", {})


# =============================================================================
# Test 3: skill_registry 能发现 skill
# =============================================================================

class TestSkillRegistry:
    """Test skill registry functionality."""

    def test_can_discover_hot_topic_fetch_skill(self):
        """Test that skill_registry can discover hot_topic_fetch_skill."""
        assert skill_registry.has("hot_topic_fetch_skill"), \
            "skill_registry should have hot_topic_fetch_skill"

        skill = skill_registry.get("hot_topic_fetch_skill")
        assert skill.skill_id == "hot_topic_fetch_skill"

    def test_list_all_skills(self):
        """Test that list_all() returns all registered skills."""
        skills = skill_registry.list_all()
        skill_ids = [s.skill_id for s in skills]

        assert "hot_topic_fetch_skill" in skill_ids, \
            "hot_topic_fetch_skill should be registered"


# =============================================================================
# Test 4: hot_topic_fetch_skill 执行成功时输出结构正确
# =============================================================================

class TestHotTopicFetchSkillExecution:
    """Test hot_topic_fetch_skill execution with mock."""

    @pytest.mark.asyncio
    async def test_execute_success_with_mock(self):
        """Test skill execute returns correct structure on success."""
        skill = HotTopicFetchSkill()

        # Mock httpx to return fake HTML
        mock_html = '''
        <html><body>
            <h3><a>测试文章标题1</a></h3>
            <h3><a>测试文章标题2</a></h3>
        </body></html>
        '''

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.text = mock_html
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value.__aexit__.return_value = AsyncMock()

            result = await skill.execute({
                "keywords": ["人工智能"],
                "engines": ["weixin"],
                "max_results_per_engine": 5
            })

        # Verify structure
        assert "status" in result
        assert "skill_id" in result
        assert result["skill_id"] == "hot_topic_fetch_skill"

        if result["status"] == "success":
            assert "data" in result
            assert "results" in result["data"]
            assert isinstance(result["data"]["results"], list)

    @pytest.mark.asyncio
    async def test_execute_with_empty_keywords_returns_failure(self):
        """Test that empty keywords returns failure."""
        skill = HotTopicFetchSkill()

        result = await skill.execute({
            "keywords": [],
        })

        assert result["status"] == "failed"
        assert result["error"]["code"] == "keywords_required"

    @pytest.mark.asyncio
    async def test_execute_with_no_keywords_returns_failure(self):
        """Test that missing keywords returns failure."""
        skill = HotTopicFetchSkill()

        result = await skill.execute({})

        assert result["status"] == "failed"
        assert "error" in result


# =============================================================================
# Test 5: Agent Result 结构验证
# =============================================================================

class TestAgentResult:
    """Test AgentResult structure."""

    def test_agent_result_success(self):
        """Test AgentResult success structure."""
        from app.agents.base import AgentResult

        result = AgentResult(
            status="success",
            agent_name="test_agent",
            data={"key": "value"}
        )

        assert result.is_success
        assert result.status == "success"
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_agent_result_failure(self):
        """Test AgentResult failure structure."""
        from app.agents.base import AgentResult

        result = AgentResult(
            status="failed",
            agent_name="test_agent",
            error={"code": "ERROR_CODE", "message": "Error message"}
        )

        assert not result.is_success
        assert result.status == "failed"
        assert result.error["code"] == "ERROR_CODE"

    def test_agent_result_to_dict(self):
        """Test AgentResult.to_dict()."""
        from app.agents.base import AgentResult

        result = AgentResult(
            status="success",
            agent_name="test_agent",
            data={"key": "value"},
            trace_id="trace-123"
        )

        d = result.to_dict()
        assert "status" in d
        assert "agent_name" in d
        assert "data" in d
        assert "trace_id" in d


# =============================================================================
# Test 6: HotTopicAgent 调用 skill
# =============================================================================

class TestHotTopicAgentSkillIntegration:
    """Test HotTopicAgent integration with skill."""

    @pytest.mark.asyncio
    async def test_agent_declares_skill_dependency(self):
        """Test that HotTopicAgent declares it uses hot_topic_fetch_skill."""
        agent = HotTopicAgent()

        assert "hot_topic_fetch_skill" in agent.supported_skills
        assert agent.get_supported_skills() == ["hot_topic_fetch_skill"]

    def test_agent_input_schema_includes_profile(self):
        """Test that agent input schema includes profile field."""
        agent = HotTopicAgent()

        assert "profile" in agent.input_schema.get("properties", {})
        assert agent.input_schema["properties"]["profile"]["description"]

    def test_agent_output_schema_includes_hot_topics(self):
        """Test that agent output schema includes hot_topics."""
        agent = HotTopicAgent()

        assert "hot_topics" in agent.output_schema.get("properties", {})


# =============================================================================
# Test 7: 保持向后兼容
# =============================================================================

class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_agent_has_execute_method(self):
        """Test that all agents have execute method."""
        agents = [
            ProfileAgent(),
            HotTopicAgent(),
            TopicPlannerAgent(),
            TitleGeneratorAgent(),
            ContentWriterAgent(),
            AuditAgent(),
        ]

        for agent in agents:
            assert hasattr(agent, "execute"), \
                f"{agent.agent_id} should have execute method"
            assert callable(agent.execute), \
                f"{agent.agent_id}.execute should be callable"

    def test_agent_has_fallback_method(self):
        """Test that all agents have fallback method."""
        agents = [
            ProfileAgent(),
            HotTopicAgent(),
            TopicPlannerAgent(),
            TitleGeneratorAgent(),
            ContentWriterAgent(),
            AuditAgent(),
        ]

        for agent in agents:
            assert hasattr(agent, "fallback"), \
                f"{agent.agent_id} should have fallback method"
            assert callable(agent.fallback), \
                f"{agent.agent_id}.fallback should be callable"

    def test_agent_has_success_failure_helpers(self):
        """Test that agents have _success and _failure helper methods."""
        agent = ProfileAgent()

        assert hasattr(agent, "_success"), "Should have _success method"
        assert hasattr(agent, "_failure"), "Should have _failure method"
