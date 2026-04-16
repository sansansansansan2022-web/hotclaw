"""
Base class for all agents.

【智能体基类】
所有业务智能体的抽象基类，定义智能体的标准接口。

核心设计原则（来自 NOTICE.md）：
- 智能体是工作流节点，负责单一业务任务
- 有清晰的输入/输出定义
- 返回结构化 JSON 数据
- 可以调用技能（Skills）
- 单一职责，不应有多重职责

Agent Contract 要求：
1. 每个 Agent 必须定义 input_schema 和 output_schema
2. 每个 Agent 的 execute() 必须返回 AgentResult
3. 每个 Agent 的失败返回必须标准化
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class AgentResult:
    """
    Standardized agent result per NOTICE.md section 8.2.

    【智能体执行结果】
    所有智能体必须返回 AgentResult，实现统一的成功/失败处理。

    Attributes:
        status: 结果状态 ("success" | "failed")
        agent_name: 智能体 ID（用于日志追踪）
        data: 成功时的结构化输出数据
        error: 失败时的错误信息
        trace_id: 追踪 ID（用于日志关联）
    """

    def __init__(
        self,
        status: str,
        agent_name: str,
        data: dict | None = None,
        error: dict | None = None,
        trace_id: str = "",
        runtime_trace: dict | None = None,
    ):
        self.status = status       # "success" 或 "failed"
        self.agent_name = agent_name
        self.data = data           # 结构化输出（供后续节点使用）
        self.error = error        # 错误信息 {code, message}
        self.trace_id = trace_id   # 追踪 ID

        self.runtime_trace = runtime_trace

    def to_dict(self) -> dict:
        """转换为字典，用于日志和序列化。"""
        return {
            "status": self.status,
            "agent_name": self.agent_name,
            "data": self.data,
            "error": self.error,
            "trace_id": self.trace_id,
            "runtime_trace": self.runtime_trace,
        }

    @property
    def is_success(self) -> bool:
        """判断是否成功执行。"""
        return self.status == "success"


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    【智能体抽象基类】
    所有具体智能体（ProfileAgent、HotTopicAgent 等）都继承此类。

    Agent Contract 要求：
    1. agent_id: 唯一标识（如 "profile_agent"）
    2. name: 中文显示名称
    3. description: 职能描述
    4. input_schema: 输入 JSON Schema 描述（dict）
    5. output_schema: 输出 JSON Schema 描述（dict）
    6. supported_skills: 该 Agent 支持调用的 Skill ID 列表
    7. execute(): 核心执行逻辑

    可选重写：
    - fallback(): 降级策略（默认返回 None，即不降级）
    """

    # 类属性：子类必须定义
    agent_id: str = ""      # 智能体唯一 ID
    name: str = ""          # 中文名称
    description: str = ""   # 职能说明

    # Agent Contract：子类必须定义
    input_schema: dict = {}   # 输入 JSON Schema 描述
    output_schema: dict = {}  # 输出 JSON Schema 描述
    supported_skills: list[str] = []  # 支持调用的 Skill ID 列表

    # 可选：系统提示词
    default_system_prompt: str = ""
    _DEFAULT_RETRYABLE_ERROR_CLASSES = {
        "connection_error",
        "provider_unavailable",
        "rate_limit",
        "timeout",
    }
    _DEFAULT_CONNECTION_ERROR_MARKERS = (
        "connection error",
        "api connection",
        "eai_again",
        "all connection attempts failed",
        "connection aborted",
        "connection reset",
        "name or service not known",
        "failed to establish a new connection",
        "temporarily unavailable",
        "network is unreachable",
        "dns",
    )

    def __init__(self, config: dict | None = None):
        """
        Args:
            config: 可选的配置字典（从数据库加载的自定义配置）
        """
        self.config = config or {}

    def get_system_prompt(self, context: dict) -> str:
        """
        Get the effective system prompt from context, falling back to default.

        【Prompt 解析】
        优先级：context["system_prompt"] > default_system_prompt
        """
        return context.get("system_prompt") or self.default_system_prompt

    def get_effective_model_config(self, context: dict | None = None) -> dict[str, Any]:
        runtime_config = (context or {}).get("agent_model_config")
        if isinstance(runtime_config, dict) and runtime_config:
            provider_id = str(runtime_config.get("provider_id") or "").strip() or "dashscope"
            model = str(runtime_config.get("model") or runtime_config.get("default_model") or "").strip()
            if not model:
                model = settings.llm_model_name.strip()
            return {
                "provider_id": provider_id,
                "model": self._normalize_model_name(provider_id, model),
                "api_key": runtime_config.get("api_key") or settings.llm_api_key,
                "base_url": runtime_config.get("base_url") or settings.llm_api_base_url,
                "timeout": runtime_config.get("timeout") or settings.llm_timeout,
            }

        model = settings.llm_model_name.strip()
        return {
            "provider_id": "dashscope",
            "model": self._normalize_model_name("dashscope", model),
            "api_key": settings.llm_api_key,
            "base_url": settings.llm_api_base_url,
            "timeout": settings.llm_timeout,
        }

    def get_litellm_completion_kwargs(self, context: dict | None = None) -> dict[str, Any]:
        config = self.get_effective_model_config(context)
        return {
            "model": config["model"],
            "api_key": config["api_key"],
            "base_url": config["base_url"],
            "custom_llm_provider": config["provider_id"],
        }

    @staticmethod
    def _normalize_model_name(provider_id: str, model: str) -> str:
        clean_provider = (provider_id or "dashscope").strip().lower()
        clean_model = (model or "").strip()
        if not clean_model:
            return clean_model

        if clean_provider == "dashscope":
            return clean_model if clean_model.startswith("dashscope/") else f"dashscope/{clean_model}"
        if clean_provider == "openai" and clean_model.startswith("openai/"):
            return clean_model.split("/", 1)[1]
        if clean_provider == "compatible" and clean_model.startswith("compatible/"):
            return clean_model.split("/", 1)[1]
        return clean_model

    def _ensure_runtime_trace(self, context: dict | None = None) -> dict[str, Any]:
        context = context if isinstance(context, dict) else {}
        trace = context.get("_agent_runtime_trace")
        if isinstance(trace, dict):
            return trace

        model_config = self.get_effective_model_config(context)
        trace = {
            "provider": model_config.get("provider_id"),
            "model": model_config.get("model"),
            "retry_count": 0,
            "prompt_tokens": None,
            "completion_tokens": None,
            "error_class": None,
            "error_message": None,
            "fallback_used": False,
        }
        context["_agent_runtime_trace"] = trace
        return trace

    def _attach_runtime_trace(
        self,
        result: AgentResult,
        context: dict | None = None,
        *,
        fallback_used: bool = False,
    ) -> AgentResult:
        trace = dict(self._ensure_runtime_trace(context))
        trace["fallback_used"] = bool(trace.get("fallback_used")) or fallback_used
        result.runtime_trace = trace
        return result

    def _classify_llm_error(
        self,
        exc: Exception,
        retryable_error_markers: tuple[str, ...] | None = None,
    ) -> str:
        if isinstance(exc, asyncio.TimeoutError):
            return "timeout"

        message = str(exc).lower()
        markers = retryable_error_markers or self._DEFAULT_CONNECTION_ERROR_MARKERS
        if any(marker in message for marker in markers):
            return "connection_error"
        if any(marker in message for marker in ("rate limit", "too many requests", "429")):
            return "rate_limit"
        if any(marker in message for marker in ("timed out", "timeout", "time out")):
            return "timeout"
        if any(marker in message for marker in ("service unavailable", "provider unavailable", "overloaded")):
            return "provider_unavailable"
        return "unknown"

    def _extract_usage(self, response: Any) -> tuple[int | None, int | None]:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")

        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")

        try:
            prompt_value = int(prompt_tokens) if prompt_tokens is not None else None
        except (TypeError, ValueError):
            prompt_value = None
        try:
            completion_value = int(completion_tokens) if completion_tokens is not None else None
        except (TypeError, ValueError):
            completion_value = None
        return prompt_value, completion_value

    async def run_litellm_completion(
        self,
        *,
        context: dict | None,
        completion_callable: Callable[..., Awaitable[Any]],
        messages: list[dict[str, Any]],
        timeout: float | int | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
        retryable_error_classes: set[str] | None = None,
        retryable_error_markers: tuple[str, ...] | None = None,
        **kwargs: Any,
    ) -> Any:
        context = context if isinstance(context, dict) else {}
        trace = self._ensure_runtime_trace(context)
        model_config = self.get_effective_model_config(context)
        runtime_policy = context.get("runtime_policy") if isinstance(context.get("runtime_policy"), dict) else {}

        resolved_timeout = timeout if timeout is not None else model_config.get("timeout") or settings.llm_timeout
        retries = max_retries if max_retries is not None else int(
            runtime_policy.get("max_retries", getattr(settings, "llm_max_retries", 1))
        )
        backoff = retry_backoff_seconds if retry_backoff_seconds is not None else float(
            runtime_policy.get(
                "retry_backoff_seconds",
                getattr(settings, "llm_retry_backoff_seconds", 0.6),
            )
        )
        retryable_classes = retryable_error_classes or set(self._DEFAULT_RETRYABLE_ERROR_CLASSES)

        trace.update(
            {
                "provider": model_config.get("provider_id"),
                "model": model_config.get("model"),
                "timeout_seconds": float(resolved_timeout),
                "retry_count": 0,
                "error_class": None,
                "error_message": None,
            }
        )

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                response = await completion_callable(
                    messages=messages,
                    timeout=resolved_timeout,
                    **self.get_litellm_completion_kwargs(context),
                    **kwargs,
                )
                prompt_tokens, completion_tokens = self._extract_usage(response)
                trace.update(
                    {
                        "retry_count": attempt,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "error_class": None,
                        "error_message": None,
                    }
                )
                return response
            except Exception as exc:
                last_error = exc
                error_class = self._classify_llm_error(exc, retryable_error_markers)
                trace.update(
                    {
                        "retry_count": attempt,
                        "error_class": error_class,
                        "error_message": str(exc),
                    }
                )
                if attempt >= retries or error_class not in retryable_classes:
                    raise
                await asyncio.sleep(backoff)

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM completion failed without returning a response.")

    @abstractmethod
    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """
        Execute the agent's task.

        【核心执行方法】子类必须实现

        工作流程：
        1. 解析输入（从 input_data 提取需要的字段）
        2. 构建 Prompt（合并 system_prompt + user_input）
        3. 调用 LLM 获取结果
        4. 解析 LLM 输出为结构化 JSON
        5. 返回 AgentResult

        Args:
            input_data: 本智能体需要的输入数据（由 Workspace.extract_for_agent() 构建）
            context: 工作空间上下文（包含 system_prompt 和前置节点输出）

        Returns:
            AgentResult: 包含 status/data/error
        """
        ...

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """
        Fallback strategy when execution fails.

        【降级策略】
        当 execute() 抛出异常或返回失败结果时，编排引擎会调用此方法。

        默认返回 None（不降级，直接失败）。
        子类可重写实现降级逻辑。

        Args:
            error: 抛出的异常对象
            input_data: 原始输入数据

        Returns:
            降级后的结果，None 表示不降级
        """
        return None

    # ========== 辅助方法 ==========

    def _success(self, data: dict, trace_id: str = "") -> AgentResult:
        """
        构建成功结果。

        使用示例：
            return self._success({"domain": "科技", "target_audience": "年轻人"})
        """
        return AgentResult(
            status="success",
            agent_name=self.agent_id,
            data=data,
            trace_id=trace_id,
        )

    def _failure(self, code: str, message: str, trace_id: str = "") -> AgentResult:
        """
        构建失败结果。

        使用示例：
            return self._failure("LLM_PARSE_ERROR", "无法解析 JSON 输出")
        """
        return AgentResult(
            status="failed",
            agent_name=self.agent_id,
            error={"code": code, "message": message},
            trace_id=trace_id,
        )

    def get_input_schema(self) -> dict:
        """获取输入 Schema 描述。"""
        return self.input_schema

    def get_output_schema(self) -> dict:
        """获取输出 Schema 描述。"""
        return self.output_schema

    def get_supported_skills(self) -> list[str]:
        """获取支持的 Skill ID 列表。"""
        return self.supported_skills

    def get_contract(self) -> dict:
        """获取完整的 Agent Contract 描述。"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "supported_skills": self.supported_skills,
        }
