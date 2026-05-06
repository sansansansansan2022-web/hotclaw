"""LLM Provider 单元测试。

测试 LLM 网关层的各个组件：
- DashScopeProvider
- OpenAIProvider
- OpenAICompatibleProvider
- LLMGateway
- 异常类
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.base import LLMResponse, LLMCallOptions, LLMCallMeta
from app.llm.exceptions import (
    LLMTimeoutError,
    LLMAPIError,
    LLMConfigurationError,
    LLMCallError,
    LLMParseError,
    LLMRateLimitError,
)
from app.llm.config import LLMConfig
from app.llm.providers.dashscope import DashScopeProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.compatible import OpenAICompatibleProvider
from app.llm.providers.deepseek import DeepSeekProvider
from app.llm.gateway import LLMGateway


# =============================================================================
# DashScopeProvider Tests
# =============================================================================

class TestDashScopeProvider:
    """DashScopeProvider 单元测试"""

    @pytest.fixture
    def provider(self):
        """创建测试 Provider 实例"""
        return DashScopeProvider(
            api_key="test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=30,
        )

    def test_supports_model(self, provider):
        """测试模型支持检查"""
        assert provider.supports_model("qwen3.5-plus")
        assert provider.supports_model("dashscope/qwen3.5-plus")
        assert provider.supports_model("qwen/qwen3.5-plus")
        assert provider.supports_model("qwen-turbo")
        assert not provider.supports_model("gpt-4")
        assert not provider.supports_model("claude-3")

    def test_get_model_name(self, provider):
        """测试模型名格式化"""
        options = LLMCallOptions(model="qwen3.5-plus")
        assert provider.get_model_name(options) == "dashscope/qwen3.5-plus"

        options = LLMCallOptions(model="dashscope/qwen-turbo")
        assert provider.get_model_name(options) == "dashscope/qwen-turbo"

        options = LLMCallOptions()
        assert provider.get_model_name(options) == "dashscope/qwen3.5-plus"

    def test_build_messages(self, provider):
        """测试消息构建"""
        options = LLMCallOptions(system_prompt="你是助手")
        messages = provider.build_messages("你好", options)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "你是助手"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "你好"

    def test_build_messages_with_existing_messages(self, provider):
        """测试使用预构建消息列表"""
        existing_messages = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
        ]
        options = LLMCallOptions(system_prompt="忽略这个", messages=existing_messages)
        messages = provider.build_messages("忽略这个", options)

        assert messages == existing_messages

    @pytest.mark.asyncio
    async def test_complete_success(self, provider):
        """测试成功调用"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="测试响应"))]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

        with patch("app.llm.providers.dashscope.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            meta = LLMCallMeta(agent_id="test_agent", trace_id="tr_test")
            result = await provider.complete(
                prompt="测试",
                options=LLMCallOptions(system_prompt="你是一个助手"),
                meta=meta,
            )

            assert result.content == "测试响应"
            assert result.provider == "dashscope"
            assert result.model == "dashscope/qwen3.5-plus"
            assert result.prompt_tokens == 10
            assert result.completion_tokens == 20
            assert result.total_tokens == 30
            assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_complete_timeout(self, provider):
        """测试超时处理"""
        with patch("app.llm.providers.dashscope.litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = TimeoutError("Connection timeout")

            meta = LLMCallMeta(agent_id="test_agent", trace_id="tr_test")

            with pytest.raises(LLMTimeoutError) as exc_info:
                await provider.complete(
                    prompt="测试",
                    options=LLMCallOptions(system_prompt="你是一个助手"),
                    meta=meta,
                )

            assert "dashscope" in str(exc_info.value)
            assert exc_info.value.code == 3001
            assert exc_info.value.details["agent_id"] == "test_agent"
            assert exc_info.value.details["timeout_seconds"] == 30

    @pytest.mark.asyncio
    async def test_complete_api_error(self, provider):
        """测试 API 错误处理"""
        with patch("app.llm.providers.dashscope.litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("API rate limit exceeded")

            meta = LLMCallMeta(agent_id="test_agent", trace_id="tr_test")

            with pytest.raises(LLMAPIError) as exc_info:
                await provider.complete(
                    prompt="测试",
                    options=LLMCallOptions(system_prompt="你是一个助手"),
                    meta=meta,
                )

            assert "rate limit" in str(exc_info.value)
            assert exc_info.value.code == 3002
            assert exc_info.value.details["provider"] == "dashscope"

    def test_configuration_error(self):
        """测试配置错误"""
        with pytest.raises(LLMConfigurationError) as exc_info:
            DashScopeProvider(api_key="", base_url="")

        assert exc_info.value.code == 3003
        assert "API key" in str(exc_info.value)


# =============================================================================
# DeepSeekProvider Tests
# =============================================================================

class TestDeepSeekProvider:
    """DeepSeekProvider 单元测试"""

    @pytest.fixture
    def provider(self):
        """创建测试 Provider 实例"""
        return DeepSeekProvider(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            timeout=30,
        )

    def test_supports_model(self, provider):
        """测试模型支持检查"""
        assert provider.supports_model("deepseek-chat")
        assert provider.supports_model("deepseek-coder")
        assert provider.supports_model("deepseek-reasoner")
        assert provider.supports_model("deepseek/deepseek-chat")
        assert not provider.supports_model("gpt-4")
        assert not provider.supports_model("qwen3.5-plus")

    def test_get_model_name(self, provider):
        """测试模型名格式化"""
        options = LLMCallOptions(model="deepseek-coder")
        assert provider.get_model_name(options) == "deepseek-coder"

        options = LLMCallOptions(model="deepseek/deepseek-chat")
        assert provider.get_model_name(options) == "deepseek/deepseek-chat"

        options = LLMCallOptions()
        assert provider.get_model_name(options) == "deepseek-chat"

    def test_build_messages(self, provider):
        """测试消息构建"""
        options = LLMCallOptions(system_prompt="你是助手")
        messages = provider.build_messages("你好", options)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "你是助手"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "你好"

    @pytest.mark.asyncio
    async def test_complete_success(self, provider):
        """测试成功调用"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="测试响应"))]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

        with patch("app.llm.providers.deepseek.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            meta = LLMCallMeta(agent_id="test_agent", trace_id="tr_test")
            result = await provider.complete(
                prompt="测试",
                options=LLMCallOptions(system_prompt="你是一个助手"),
                meta=meta,
            )

            assert result.content == "测试响应"
            assert result.provider == "deepseek"
            assert result.model == "deepseek-chat"
            assert result.prompt_tokens == 10
            assert result.completion_tokens == 20
            assert result.total_tokens == 30
            assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_complete_timeout(self, provider):
        """测试超时处理"""
        with patch("app.llm.providers.deepseek.litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = TimeoutError("Connection timeout")

            meta = LLMCallMeta(agent_id="test_agent", trace_id="tr_test")

            with pytest.raises(LLMTimeoutError) as exc_info:
                await provider.complete(
                    prompt="测试",
                    options=LLMCallOptions(system_prompt="你是一个助手"),
                    meta=meta,
                )

            assert "deepseek" in str(exc_info.value)
            assert exc_info.value.code == 3001
            assert exc_info.value.details["agent_id"] == "test_agent"
            assert exc_info.value.details["timeout_seconds"] == 30

    @pytest.mark.asyncio
    async def test_complete_api_error(self, provider):
        """测试 API 错误处理"""
        with patch("app.llm.providers.deepseek.litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("API rate limit exceeded")

            meta = LLMCallMeta(agent_id="test_agent", trace_id="tr_test")

            with pytest.raises(LLMAPIError) as exc_info:
                await provider.complete(
                    prompt="测试",
                    options=LLMCallOptions(system_prompt="你是一个助手"),
                    meta=meta,
                )

            assert "rate limit" in str(exc_info.value)
            assert exc_info.value.code == 3002
            assert exc_info.value.details["provider"] == "deepseek"

    def test_configuration_error(self):
        """测试配置错误"""
        with pytest.raises(LLMConfigurationError) as exc_info:
            DeepSeekProvider(api_key="", base_url="")

        assert exc_info.value.code == 3003
        assert "API key" in str(exc_info.value)


# =============================================================================
# OpenAIProvider Tests
# =============================================================================

class TestOpenAIProvider:
    """OpenAIProvider 单元测试"""

    @pytest.fixture
    def provider(self):
        return OpenAIProvider(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
            timeout=30,
        )

    def test_supports_model(self, provider):
        """测试模型支持检查"""
        assert provider.supports_model("gpt-4o-mini")
        assert provider.supports_model("openai/gpt-4o")
        assert provider.supports_model("o1-mini")
        assert not provider.supports_model("qwen3.5-plus")

    def test_get_model_name(self, provider):
        """测试模型名获取"""
        options = LLMCallOptions(model="gpt-4o")
        assert provider.get_model_name(options) == "gpt-4o"

        options = LLMCallOptions()
        assert provider.get_model_name(options) == "gpt-4o-mini"


# =============================================================================
# OpenAICompatibleProvider Tests
# =============================================================================

class TestOpenAICompatibleProvider:
    """OpenAICompatibleProvider 单元测试"""

    @pytest.fixture
    def provider(self):
        return OpenAICompatibleProvider(
            api_key="test-key",
            base_url="http://localhost:8000/v1",
            timeout=120,
        )

    def test_supports_model(self, provider):
        """兼容模式支持所有模型"""
        assert provider.supports_model("meta-llama/Llama-3-70B")
        assert provider.supports_model("mistralai/Mistral-7B-Instruct")
        assert provider.supports_model("qwen2.5-72B")

    def test_get_model_name_empty(self, provider):
        """测试空模型名"""
        options = LLMCallOptions()
        # 兼容模式允许空模型名
        assert provider.get_model_name(options) == ""


# =============================================================================
# LLMGateway Tests
# =============================================================================

class TestLLMGateway:
    """LLMGateway 单元测试"""

    @pytest.fixture
    def mock_config(self):
        """创建测试配置"""
        return LLMConfig(
            default_provider="dashscope",
            dashscope_api_key="test-key",
            dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            dashscope_model="qwen3.5-plus",
            timeout=60,
        )

    @pytest.mark.asyncio
    async def test_gateway_delegates_to_provider(self, mock_config):
        """测试 Gateway 正确委托给 Provider"""
        gateway = LLMGateway(config=mock_config)

        # Mock 响应
        mock_response = LLMResponse(
            content="test response",
            model="dashscope/qwen3.5-plus",
            provider="dashscope",
            latency_ms=100,
        )

        # 创建一个正确配置的 Mock Provider
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)
        gateway._providers["dashscope"] = mock_provider

        result = await gateway.complete(
            agent_id="test_agent",
            prompt="test",
            options=LLMCallOptions(system_prompt="you are assistant"),
            provider="dashscope",
        )

        assert result.content == "test response"
        assert result.provider == "dashscope"
        # 验证 provider.complete 被调用
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_gateway_unknown_provider(self, mock_config):
        """测试未知 Provider 抛出错误"""
        gateway = LLMGateway(config=mock_config)
        gateway._providers = {}

        with pytest.raises(LLMConfigurationError) as exc_info:
            await gateway.complete(
                agent_id="test_agent",
                prompt="test",
                options=LLMCallOptions(system_prompt="you are assistant"),
                provider="unknown",
            )

        assert "not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_gateway_default_provider(self, mock_config):
        """测试默认 Provider"""
        gateway = LLMGateway(config=mock_config)

        mock_response = LLMResponse(
            content="default response",
            model="dashscope/qwen3.5-plus",
            provider="dashscope",
            latency_ms=100,
        )

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)
        gateway._providers["dashscope"] = mock_provider

        # 不指定 provider，使用默认
        result = await gateway.complete(
            agent_id="test_agent",
            prompt="test",
            options=LLMCallOptions(system_prompt="you are assistant"),
        )

        assert result.content == "default response"

    def test_get_available_providers(self, mock_config):
        """测试获取可用 Provider 列表"""
        gateway = LLMGateway(config=mock_config)
        providers = gateway.get_available_providers()

        assert "dashscope" in providers

    def test_is_provider_available(self, mock_config):
        """测试检查 Provider 可用性"""
        gateway = LLMGateway(config=mock_config)

        assert gateway.is_provider_available("dashscope")
        assert not gateway.is_provider_available("openai")


# =============================================================================
# LLMExceptions Tests
# =============================================================================

class TestLLMExceptions:
    """异常类单元测试"""

    def test_llm_timeout_error_format(self):
        """测试超时异常格式"""
        error = LLMTimeoutError(
            provider="dashscope",
            model="qwen3.5-plus",
            timeout=60,
            agent_id="profile_agent",
            latency_ms=60123.45,
        )

        assert "60s" in str(error)
        assert error.code == 3001
        assert error.details["provider"] == "dashscope"
        assert error.details["latency_ms"] == 60123.45
        assert error.details["agent_id"] == "profile_agent"

    def test_llm_api_error_format(self):
        """测试 API 错误格式"""
        error = LLMAPIError(
            provider="openai",
            model="gpt-4o-mini",
            message="Invalid API key",
            agent_id="test_agent",
            latency_ms=100.5,
            status_code=401,
        )

        assert "Invalid API key" in str(error)
        assert error.code == 3002
        assert error.details["status_code"] == 401

    def test_llm_configuration_error_format(self):
        """测试配置错误格式"""
        error = LLMConfigurationError(
            provider="dashscope",
            message="API key is required",
            missing_field="dashscope_api_key",
        )

        assert "API key" in str(error)
        assert error.code == 3003
        assert error.details["missing_field"] == "dashscope_api_key"

    def test_llm_parse_error_format(self):
        """测试解析错误格式"""
        error = LLMParseError(
            provider="dashscope",
            model="qwen3.5-plus",
            raw_response="这不是 JSON {",
            parse_error="Expecting property name",
        )

        assert "Failed to parse" in str(error)
        assert error.code == 3004
        assert "不是 JSON" in error.details["raw_response_preview"]

    def test_llm_rate_limit_error_format(self):
        """测试速率限制错误格式"""
        error = LLMRateLimitError(
            provider="openai",
            model="gpt-4o-mini",
            agent_id="test_agent",
            latency_ms=100,
            retry_after=60,
        )

        assert "Rate limit" in str(error)
        assert error.code == 3005
        assert error.details["retry_after_seconds"] == 60

    def test_exception_to_dict(self):
        """测试异常转字典"""
        error = LLMCallError(
            message="Test error",
            details={"key": "value"},
        )

        result = error.to_dict()
        assert result["error_type"] == "LLMCallError"
        assert result["message"] == "Test error"
        assert result["details"]["key"] == "value"


# =============================================================================
# LLMCallOptions Tests
# =============================================================================

class TestLLMCallOptions:
    """LLMCallOptions 单元测试"""

    def test_default_values(self):
        """测试默认值"""
        options = LLMCallOptions()

        assert options.system_prompt == ""
        assert options.messages is None
        assert options.temperature == 0.7
        assert options.max_tokens is None
        assert options.model is None

    def test_custom_values(self):
        """测试自定义值"""
        options = LLMCallOptions(
            system_prompt="你是一个助手",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
            max_tokens=1000,
            model="gpt-4",
        )

        assert options.system_prompt == "你是一个助手"
        assert len(options.messages) == 1
        assert options.temperature == 0.5
        assert options.max_tokens == 1000
        assert options.model == "gpt-4"


# =============================================================================
# LLMConfig Tests
# =============================================================================

class TestLLMConfig:
    """LLMConfig 单元测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = LLMConfig()

        assert config.default_provider == "dashscope"
        assert config.timeout == 60
        assert config.max_retries == 2

    def test_get_default_model(self):
        """测试获取默认模型"""
        config = LLMConfig(
            dashscope_model="qwen3.5-plus",
            openai_model="gpt-4o-mini",
        )

        assert config.get_default_model("dashscope") == "qwen3.5-plus"
        assert config.get_default_model("openai") == "gpt-4o-mini"
        assert config.get_default_model("unknown") == ""

    def test_is_provider_configured(self):
        """测试 Provider 配置检查"""
        config = LLMConfig(
            dashscope_api_key="test-key",
            openai_api_key="",
        )

        assert config.is_provider_configured("dashscope")
        assert not config.is_provider_configured("openai")
        assert not config.is_provider_configured("compatible")

    def test_get_provider_config(self):
        """测试获取 Provider 配置"""
        config = LLMConfig(
            dashscope_api_key="ds-key",
            dashscope_base_url="https://ds.example.com",
            dashscope_model="qwen-max",
        )

        ds_config = config.get_provider_config("dashscope")
        assert ds_config["api_key"] == "ds-key"
        assert ds_config["base_url"] == "https://ds.example.com"
        assert ds_config["model"] == "qwen-max"


# =============================================================================
# Integration-like Tests (with mocks)
# =============================================================================

class TestLLMIntegration:
    """集成测试（使用 Mock）"""

    @pytest.mark.asyncio
    async def test_profile_agent_like_flow(self):
        """模拟 ProfileAgent 的完整调用流程"""
        config = LLMConfig(
            default_provider="dashscope",
            dashscope_api_key="test-key",
            timeout=60,
        )

        gateway = LLMGateway(config=config)

        # Mock 响应
        mock_response = LLMResponse(
            content='{"domain": "test", "subdomain": "test"}',
            model="dashscope/qwen3.5-plus",
            provider="dashscope",
            prompt_tokens=50,
            completion_tokens=30,
            total_tokens=80,
            latency_ms=1500,
        )

        # 使用 async 函数模拟 Provider.complete 方法
        async def mock_complete(prompt, options, meta):
            return mock_response

        gateway._providers["dashscope"].complete = mock_complete

        # 执行调用
        result = await gateway.complete(
            agent_id="profile_agent",
            prompt="parse account positioning",
            options=LLMCallOptions(
                system_prompt="you are an analyst",
                temperature=0.7,
            ),
        )

        # 验证
        assert result.content == '{"domain": "test", "subdomain": "test"}'
        assert result.latency_ms == 1500
        assert result.total_tokens == 80
