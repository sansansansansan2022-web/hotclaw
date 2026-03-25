"""OpenAI 兼容模式 Provider（vLLM、Ollama 等）"""

import time
from typing import Any

import litellm

from app.llm.base import LLMProvider, LLMResponse, LLMCallOptions, LLMCallMeta
from app.llm.exceptions import LLMTimeoutError, LLMAPIError, LLMConfigurationError


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI 兼容模式 Provider

    支持以下兼容 OpenAI API 的服务:
    - vLLM (本地 GPU 加速推理)
    - Ollama (本地 LLM 推理)
    - LM Studio (本地模型服务)
    - FastChat / ChatGLM 部署
    - 任何实现 /v1/chat/completions 的服务

    环境变量:
    - COMPATIBLE_API_KEY (可选，很多本地服务不需要)
    - COMPATIBLE_BASE_URL (如 http://localhost:8000/v1)
    """

    name = "compatible"

    SUPPORTED_MODELS: set[str] = set()
    """动态支持，取决于部署的模型"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://localhost:8000/v1",
        timeout: int = 120,  # 本地服务可能需要更长超时
    ):
        self.api_key = api_key or "not-needed"
        self.base_url = base_url
        self.timeout = timeout

        if not self.base_url:
            raise LLMConfigurationError(
                provider=self.name,
                message="Base URL is required for compatible provider",
                missing_field="compatible_base_url",
            )

    def supports_model(self, model: str) -> bool:
        """兼容模式支持所有模型（由服务端决定）"""
        # 移除 prefix
        clean_model = model.replace("compatible/", "")
        # 允许任意模型名
        return bool(clean_model)

    def get_model_name(self, options: LLMCallOptions) -> str:
        """获取模型名"""
        if options.model:
            return options.model
        # 如果没有指定模型，返回空字符串让服务端决定
        return ""

    async def complete(
        self,
        prompt: str,
        options: LLMCallOptions,
        meta: LLMCallMeta,
    ) -> LLMResponse:
        """执行兼容模式 LLM 调用"""
        model = self.get_model_name(options)
        messages = self.build_messages(prompt, options)

        start_time = time.perf_counter()

        # 构建请求参数
        kwargs = {
            "model": model if model else "default",
            "messages": messages,
            "timeout": self.timeout,
            "temperature": options.temperature,
        }

        # 只有当 api_key 不是默认值时才传递
        if self.api_key and self.api_key != "not-needed":
            kwargs["api_key"] = self.api_key

        kwargs["base_url"] = self.base_url

        if options.max_tokens:
            kwargs["max_tokens"] = options.max_tokens

        try:
            response = await litellm.acompletion(**kwargs)

            latency_ms = (time.perf_counter() - start_time) * 1000

            return self._parse_response(response, model, latency_ms)

        except TimeoutError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            raise LLMTimeoutError(
                provider=self.name,
                model=model,
                timeout=self.timeout,
                agent_id=meta.agent_id,
                latency_ms=latency_ms,
            ) from e

        except litellm.Timeout as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            raise LLMTimeoutError(
                provider=self.name,
                model=model,
                timeout=self.timeout,
                agent_id=meta.agent_id,
                latency_ms=latency_ms,
            ) from e

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            error_msg = str(e)
            status_code = self._extract_status_code(e)

            raise LLMAPIError(
                provider=self.name,
                model=model,
                message=error_msg,
                agent_id=meta.agent_id,
                latency_ms=latency_ms,
                status_code=status_code,
            ) from e

    def _parse_response(
        self,
        response: Any,
        model: str,
        latency_ms: float,
    ) -> LLMResponse:
        """解析 litellm 响应"""
        content = ""
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            content = getattr(message, "content", "") or ""

        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0

        return LLMResponse(
            content=content,
            model=model,
            provider=self.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            raw_response=response,
        )

    def _extract_status_code(self, error: Exception) -> int | None:
        """从异常中提取状态码"""
        error_str = str(error)

        import re

        patterns = [
            r"status_code[=:]?\s*(\d+)",
            r"HTTP\s*(\d{3})",
        ]

        for pattern in patterns:
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                return int(match.group(1))

        if "timeout" in error_str.lower():
            return 408
        if "connection" in error_str.lower():
            return 0  # 连接错误
        if "refused" in error_str.lower():
            return 0  # 连接被拒绝

        return None
