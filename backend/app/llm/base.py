"""LLM Provider 抽象基类和核心数据类型。

统一抽象层，定义 LLM 调用标准接口，适配多种 Provider。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """LLM 调用结果"""

    content: str
    """原始文本内容"""

    model: str
    """实际调用的模型"""

    provider: str
    """Provider 名称"""

    prompt_tokens: int = 0
    """输入 token 数"""

    completion_tokens: int = 0
    """输出 token 数"""

    total_tokens: int = 0
    """总 token 数"""

    latency_ms: float = 0.0
    """调用延迟（毫秒）"""

    raw_response: Any = None
    """原始响应（可选）"""


@dataclass
class LLMCallOptions:
    """LLM 调用选项"""

    system_prompt: str = ""
    """系统提示词"""

    messages: list[dict] | None = None
    """消息列表（与 system_prompt+prompt 二选一）"""

    temperature: float = 0.7
    """温度参数，控制随机性"""

    max_tokens: int | None = None
    """最大输出 token 数"""

    model: str | None = None
    """可选：覆盖默认模型"""


@dataclass
class LLMCallMeta:
    """LLM 调用元信息（用于日志追踪）"""

    agent_id: str
    """调用方 agent ID"""

    trace_id: str = ""
    """追踪 ID"""

    request_id: str = ""
    """请求 ID"""


class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    name: str = ""
    """Provider 标识，如 "openai", "dashscope", "compatible" """

    SUPPORTED_MODELS: set[str] = field(default_factory=set)
    """支持模型列表"""

    def supports_model(self, model: str) -> bool:
        """
        检查是否支持该模型

        Args:
            model: 模型名称（可能带 prefix，如 "dashscope/qwen3.5-plus"）

        Returns:
            是否支持
        """
        # 移除 provider prefix
        clean_model = model.split("/")[-1] if "/" in model else model
        return clean_model in self.SUPPORTED_MODELS

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        options: LLMCallOptions,
        meta: LLMCallMeta,
    ) -> LLMResponse:
        """
        执行补全调用

        Args:
            prompt: 用户输入提示词（当 messages 为 None 时使用）
            options: 调用选项
            meta: 调用元信息

        Returns:
            LLMResponse

        Raises:
            LLMTimeoutError: 调用超时
            LLMAPIError: API 调用失败
        """
        ...

    def get_model_name(self, options: LLMCallOptions) -> str:
        """
        获取标准化的模型名称（子类可覆盖）

        Args:
            options: 调用选项

        Returns:
            标准化后的模型名
        """
        if options.model:
            return options.model
        if self.SUPPORTED_MODELS:
            return next(iter(self.SUPPORTED_MODELS))
        return ""

    def build_messages(
        self,
        prompt: str,
        options: LLMCallOptions,
    ) -> list[dict]:
        """
        构建消息列表

        Args:
            prompt: 用户输入
            options: 调用选项

        Returns:
            消息列表
        """
        if options.messages:
            return options.messages

        messages = []
        if options.system_prompt:
            messages.append({"role": "system", "content": options.system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
