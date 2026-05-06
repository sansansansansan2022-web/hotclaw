"""DeepSeek Provider 实现"""

import time
from typing import Any

import litellm

from app.llm.base import LLMProvider, LLMResponse, LLMCallOptions, LLMCallMeta
from app.llm.exceptions import LLMTimeoutError, LLMAPIError, LLMConfigurationError


class DeepSeekProvider(LLMProvider):
    """
    DeepSeek API Provider

    支持模型:
    - deepseek-chat (通用对话模型)
    - deepseek-coder (代码专用模型)
    - deepseek-reasoner (R1 推理模型)

    环境变量:
    - DEEPSEEK_API_KEY
    """

    name = "deepseek"

    SUPPORTED_MODELS = {
        "deepseek-chat",
        "deepseek-coder",
        "deepseek-reasoner",
        "deepseek-r1",  # 别名
    }

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

        if not self.api_key:
            raise LLMConfigurationError(
                provider=self.name,
                message="API key is required",
                missing_field="deepseek_api_key",
            )

    def supports_model(self, model: str) -> bool:
        """检查是否支持该模型"""
        clean_model = model.replace("deepseek/", "")
        return clean_model in self.SUPPORTED_MODELS

    def get_model_name(self, options: LLMCallOptions) -> str:
        """获取模型名"""
        return options.model or "deepseek-chat"

    async def complete(
        self,
        prompt: str,
        options: LLMCallOptions,
        meta: LLMCallMeta,
    ) -> LLMResponse:
        """执行 DeepSeek LLM 调用"""
        model = self.get_model_name(options)
        messages = self.build_messages(prompt, options)

        start_time = time.perf_counter()

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                temperature=options.temperature,
                max_tokens=options.max_tokens,
            )

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
        if "rate limit" in error_str.lower() or "429" in error_str:
            return 429
        if "unauthorized" in error_str.lower() or "401" in error_str:
            return 401

        return None
