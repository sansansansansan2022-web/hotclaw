"""LLM 模块统一导出。

提供统一的 LLM 调用接口，所有 Agent 应通过此模块使用 LLM。

使用示例:
    from app.llm import LLMGateway, LLMCallOptions, LLMResponse

    gateway = LLMGateway()
    response = await gateway.complete(
        agent_id="profile_agent",
        prompt="解析以下账号定位",
        options=LLMCallOptions(system_prompt="你是一个助手"),
    )
"""

# 核心类型
from app.llm.base import (
    LLMResponse,
    LLMCallOptions,
    LLMCallMeta,
    LLMProvider,
)

# 配置
from app.llm.config import (
    LLMConfig,
    get_llm_config,
    reload_llm_config,
)

# 异常
from app.llm.exceptions import (
    LLMCallError,
    LLMTimeoutError,
    LLMAPIError,
    LLMConfigurationError,
    LLMParseError,
    LLMRateLimitError,
)

# 网关
from app.llm.gateway import (
    LLMGateway,
    get_llm_gateway,
    reload_llm_gateway,
)

# Provider
from app.llm.providers import (
    DashScopeProvider,
    OpenAIProvider,
    OpenAICompatibleProvider,
)

# 单例快捷访问
llm_gateway = get_llm_gateway()

__all__ = [
    # 核心类型
    "LLMResponse",
    "LLMCallOptions",
    "LLMCallMeta",
    "LLMProvider",
    # 配置
    "LLMConfig",
    "get_llm_config",
    "reload_llm_config",
    # 异常
    "LLMCallError",
    "LLMTimeoutError",
    "LLMAPIError",
    "LLMConfigurationError",
    "LLMParseError",
    "LLMRateLimitError",
    # 网关
    "LLMGateway",
    "get_llm_gateway",
    "reload_llm_gateway",
    "llm_gateway",
    # Provider
    "DashScopeProvider",
    "OpenAIProvider",
    "OpenAICompatibleProvider",
]
