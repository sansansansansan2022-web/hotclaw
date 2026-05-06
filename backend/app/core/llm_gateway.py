"""
统一的 LLM 网关入口（``app.core.llm_gateway``）。

【为什么放在 app/core？】
- ``app.llm`` 包负责 Provider/异常/配置等底层抽象。
- ``app.core.llm_gateway`` 是面向业务层（agents、services）的稳定入口。
  PR 1 起所有 agent 必须从这里 import ``llm_gateway``，方便未来在不动 agent
  的情况下替换底层实现（fallback chain、metrics、cache 等）。

使用示例::

    from app.core.llm_gateway import llm_gateway, LLMGatewayError

    response = await llm_gateway.complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        agent_id="profile_agent",
        response_format="json",
    )
    data = response.parsed  # already JSON-decoded; markdown 围栏已剥离
"""

from __future__ import annotations

from app.llm.base import LLMCallOptions, LLMResponse
from app.llm.exceptions import (
    LLMAPIError,
    LLMCallError,
    LLMConfigurationError,
    LLMParseError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.gateway import (
    LLMGateway,
    get_llm_gateway,
    reload_llm_gateway,
)

# 网关错误的"业务侧别名"。所有 LLM 失败统一是 ``LLMCallError`` 子类，
# 业务层只 catch 这个名字即可，方便日后细分时不动 agent 代码。
LLMGatewayError = LLMCallError


# 全局单例（业务层只 import 这个名字）
llm_gateway: LLMGateway = get_llm_gateway()


__all__ = [
    "llm_gateway",
    "LLMGateway",
    "LLMResponse",
    "LLMCallOptions",
    "LLMGatewayError",
    "LLMCallError",
    "LLMConfigurationError",
    "LLMParseError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMAPIError",
    "get_llm_gateway",
    "reload_llm_gateway",
]
