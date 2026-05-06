"""LLM 相关异常类。

提供细粒度的异常类型，方便调用方精确处理。
"""

from typing import Any


class LLMCallError(Exception):
    """LLM 调用基类异常"""

    code: int = 3000
    """错误码：3xxx 表示 LLM 相关错误"""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict:
        """转换为字典格式，用于日志和响应"""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class LLMTimeoutError(LLMCallError):
    """LLM 调用超时"""

    code = 3001

    def __init__(
        self,
        provider: str,
        model: str,
        timeout: int,
        agent_id: str,
        latency_ms: float,
    ):
        details = {
            "provider": provider,
            "model": model,
            "timeout_seconds": timeout,
            "agent_id": agent_id,
            "latency_ms": round(latency_ms, 2),
        }
        message = (
            f"LLM call timed out after {timeout}s "
            f"(provider={provider}, model={model}, agent={agent_id})"
        )
        super().__init__(message=message, details=details)


class LLMAPIError(LLMCallError):
    """LLM API 调用失败"""

    code = 3002

    def __init__(
        self,
        provider: str,
        model: str,
        message: str,
        agent_id: str,
        latency_ms: float,
        status_code: int | None = None,
    ):
        details = {
            "provider": provider,
            "model": model,
            "agent_id": agent_id,
            "latency_ms": round(latency_ms, 2),
            "status_code": status_code,
        }
        full_message = f"LLM API error from {provider}/{model}: {message}"
        super().__init__(message=full_message, details=details)


class LLMConfigurationError(LLMCallError):
    """LLM 配置错误"""

    code = 3003

    def __init__(
        self,
        provider: str,
        message: str,
        missing_field: str | None = None,
    ):
        details = {
            "provider": provider,
            "missing_field": missing_field,
        }
        full_message = f"LLM configuration error for {provider}: {message}"
        super().__init__(message=full_message, details=details)


class LLMParseError(LLMCallError):
    """LLM 响应解析错误"""

    code = 3004

    def __init__(
        self,
        provider: str,
        model: str,
        raw_response: str,
        parse_error: str,
    ):
        details = {
            "provider": provider,
            "model": model,
            "raw_response_preview": raw_response[:500] if raw_response else "",
            "parse_error": parse_error,
        }
        message = f"Failed to parse LLM response: {parse_error}"
        super().__init__(message=message, details=details)


class LLMRateLimitError(LLMCallError):
    """LLM 速率限制"""

    code = 3005

    def __init__(
        self,
        provider: str,
        model: str,
        agent_id: str,
        latency_ms: float,
        retry_after: int | None = None,
    ):
        details = {
            "provider": provider,
            "model": model,
            "agent_id": agent_id,
            "latency_ms": round(latency_ms, 2),
            "status_code": 429,
            "retry_after_seconds": retry_after,
        }
        message = f"Rate limit exceeded for {provider}/{model}"
        super().__init__(message=message, details=details)
