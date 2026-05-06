"""
LLM Gateway - 统一 LLM 调用入口。

【LLM 网关】
所有 Agent 的 LLM 调用都必须经过此网关，负责：
- Provider 路由：从数据库 / .env 加载默认 Provider
- 请求统一：JSON 解析、重试、结构化日志、异常转换
- 后续扩展位：fallback chain（PR 1 不实现）

新代码应使用 ``llm_gateway.complete(messages=[...], agent_id=...)`` 形式调用，
返回的 ``LLMResponse.parsed`` 自动包含 JSON 解析结果。

老代码兼容签名 ``complete(agent_id=..., prompt=..., options=...)`` 继续可用，
方便 ``app/services`` 层不动也能跑（保留至 PR 1 之后再清理）。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.core.logger import get_logger
from app.llm.base import LLMProvider, LLMResponse, LLMCallOptions, LLMCallMeta
from app.llm.config import LLMConfig, get_llm_config
from app.llm.exceptions import (
    LLMCallError,
    LLMConfigurationError,
    LLMParseError,
    LLMRateLimitError,
    LLMAPIError,
    LLMTimeoutError,
)
from app.llm.providers.dashscope import DashScopeProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.compatible import OpenAICompatibleProvider
from app.llm.providers.deepseek import DeepSeekProvider

logger = get_logger(__name__)


_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMGateway:
    """
    统一 LLM 网关门面。

    支持配置来源：
    1. 数据库（高优先级）
    2. .env 环境变量

    主入口：``complete(messages, agent_id, response_format="json")``。
    """

    # PR 1 暂不实现，仅保留接口位
    fallback_chain: list[str] = []

    def __init__(self, config: LLMConfig | None = None, use_db_config: bool = True):
        self.config = config or get_llm_config()
        self._providers: dict[str, LLMProvider] = {}
        self._db_config: dict[str, dict] = {}
        self._default_provider: str = self.config.default_provider
        self._initialized: bool = False

        if use_db_config:
            self._load_db_config()

        self._init_providers()

    # ------------------------------------------------------------------ init

    async def initialize(self, db: Any | None = None) -> None:
        """
        生命周期钩子：在 FastAPI startup 阶段重新加载 DB 配置。

        ``db`` 参数当前未使用（gateway 内部自行开 session），保留方便后续注入。
        """
        # 在事件循环里直接调用 async 加载，避免 _load_db_config 用 ThreadPoolExecutor
        await self._load_db_config_async()
        self._init_providers()
        self._initialized = True
        logger.info(
            "llm_gateway_initialized",
            providers=list(self._providers.keys()),
            default_provider=self._default_provider,
        )

    async def _load_db_config_async(self) -> None:
        try:
            from sqlalchemy import select
            from app.db.session import async_session_factory
            from app.models.tables import LLMProviderModel

            async with async_session_factory() as session:
                result = await session.execute(
                    select(LLMProviderModel).where(LLMProviderModel.is_enabled == True)
                )
                providers = result.scalars().all()

                db_config: dict[str, dict] = {}
                default_provider: str | None = None

                for p in providers:
                    db_config[p.provider_id] = {
                        "api_key": p.api_key,
                        "base_url": p.base_url,
                        "default_model": p.default_model,
                        "supported_models": p.supported_models or [],
                        "timeout": p.timeout,
                        "is_default": p.is_default,
                    }
                    if p.is_default:
                        default_provider = p.provider_id

                self._db_config = db_config
                if default_provider:
                    self._default_provider = default_provider

                if db_config:
                    logger.info(
                        "llm_db_config_loaded",
                        providers=list(db_config.keys()),
                        default_provider=self._default_provider,
                    )
        except Exception as exc:
            logger.warning(
                "llm_db_config_load_failed",
                error=str(exc),
                message="Will use .env config instead",
            )
            self._db_config = {}

    def _load_db_config(self) -> None:
        """同步 + 线程池加载（兼容首次构造时不在 event loop 内的场景）。"""
        try:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, self._load_db_config_async()).result()
        except Exception as exc:
            logger.warning(
                "llm_db_config_load_failed",
                error=str(exc),
                message="Will use .env config instead",
            )
            self._db_config = {}

    def _init_providers(self) -> None:
        def get_provider_config(provider_id: str) -> dict | None:
            if provider_id in self._db_config:
                return self._db_config[provider_id]
            return self.config.get_provider_config(provider_id)

        # 重置后重建（initialize 后 default_provider 可能变化）
        self._providers = {}

        dashscope_config = get_provider_config("dashscope")
        if dashscope_config and dashscope_config.get("api_key"):
            try:
                self._providers["dashscope"] = DashScopeProvider(
                    api_key=dashscope_config["api_key"],
                    base_url=dashscope_config.get("base_url") or self.config.dashscope_base_url,
                    timeout=dashscope_config.get("timeout") or self.config.timeout,
                )
                logger.info("llm_provider_initialized", provider="dashscope")
            except LLMConfigurationError as e:
                logger.warning("llm_provider_init_skipped", provider="dashscope", reason=str(e))

        openai_config = get_provider_config("openai")
        if openai_config and openai_config.get("api_key"):
            try:
                self._providers["openai"] = OpenAIProvider(
                    api_key=openai_config["api_key"],
                    base_url=openai_config.get("base_url") or self.config.openai_base_url,
                    timeout=openai_config.get("timeout") or self.config.timeout,
                )
                logger.info("llm_provider_initialized", provider="openai")
            except LLMConfigurationError as e:
                logger.warning("llm_provider_init_skipped", provider="openai", reason=str(e))

        deepseek_config = get_provider_config("deepseek")
        if deepseek_config and deepseek_config.get("api_key"):
            try:
                self._providers["deepseek"] = DeepSeekProvider(
                    api_key=deepseek_config["api_key"],
                    base_url=deepseek_config.get("base_url") or "https://api.deepseek.com",
                    timeout=deepseek_config.get("timeout") or self.config.timeout,
                )
                logger.info("llm_provider_initialized", provider="deepseek")
            except LLMConfigurationError as e:
                logger.warning("llm_provider_init_skipped", provider="deepseek", reason=str(e))

        compatible_config = get_provider_config("compatible")
        if compatible_config and compatible_config.get("base_url"):
            try:
                self._providers["compatible"] = OpenAICompatibleProvider(
                    api_key=compatible_config.get("api_key") or None,
                    base_url=compatible_config["base_url"],
                    timeout=compatible_config.get("timeout") or self.config.timeout,
                )
                logger.info("llm_provider_initialized", provider="compatible")
            except LLMConfigurationError as e:
                logger.warning("llm_provider_init_skipped", provider="compatible", reason=str(e))

        zhipu_config = get_provider_config("zhipu")
        if zhipu_config and zhipu_config.get("api_key"):
            try:
                self._providers["zhipu"] = OpenAICompatibleProvider(
                    api_key=zhipu_config["api_key"],
                    base_url=zhipu_config.get("base_url") or "https://open.bigmodel.cn/api/paas/v4",
                    timeout=zhipu_config.get("timeout") or self.config.timeout,
                )
                logger.info("llm_provider_initialized", provider="zhipu")
            except LLMConfigurationError as e:
                logger.warning("llm_provider_init_skipped", provider="zhipu", reason=str(e))

        if not self._providers:
            logger.warning(
                "no_llm_providers_initialized",
                message="No LLM providers configured. Check API keys in database or .env",
            )
        else:
            logger.info(
                "llm_providers_initialized",
                providers=list(self._providers.keys()),
                default_provider=self._default_provider,
            )

    # ----------------------------------------------------------------- main

    async def complete(  # noqa: C901 - kept on purpose; routing branches are flat
        self,
        *,
        agent_id: str,
        messages: list[dict] | None = None,
        prompt: str | None = None,
        system_prompt: str | None = None,
        options: LLMCallOptions | None = None,
        response_format: str | None = "json",
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        provider: str | None = None,
        retry: bool = True,
        max_retries: int | None = None,
        trace_id: str = "",
        **_unused: Any,
    ) -> LLMResponse:
        """
        统一 LLM 调用入口。

        推荐用法（PR 1 起所有 agent 都走这个）::

            response = await llm_gateway.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                agent_id="profile_agent",
                response_format="json",
            )
            data = response.parsed  # markdown 围栏已被处理

        兼容用法（早期代码继续可用）::

            response = await llm_gateway.complete(
                agent_id="account_ops_agent",
                prompt="...",
                options=LLMCallOptions(system_prompt=..., temperature=0.2),
            )

        Returns:
            LLMResponse，含 content / parsed / token / latency / provider / model / raw

        Raises:
            LLMCallError 系列（``LLMGatewayError`` 是其别名），让调用方自己降级。
        """
        # 1) 构建 LLMCallOptions
        call_options = self._build_call_options(
            messages=messages,
            prompt=prompt,
            system_prompt=system_prompt,
            options=options,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

        # 2) 选择 provider 与模型
        selected_provider = provider or self._default_provider
        provider_instance = self._providers.get(selected_provider)
        if not provider_instance:
            available = list(self._providers.keys())
            error_msg = (
                f"Provider '{selected_provider}' not available. "
                f"Available providers: {available}"
            )
            logger.error(
                "llm_call",
                agent_id=agent_id,
                provider=selected_provider,
                model=call_options.model or "auto",
                error="LLMConfigurationError",
                error_message=error_msg,
            )
            raise LLMConfigurationError(provider=selected_provider, message=error_msg)

        if not call_options.model:
            db_default = self._db_config.get(selected_provider, {}).get("default_model")
            call_options.model = db_default or self.config.get_default_model(selected_provider)

        meta = LLMCallMeta(agent_id=agent_id, trace_id=trace_id)

        # 3) 执行（带重试）
        prompt_for_provider = "" if call_options.messages else (prompt or "")
        attempts = 1 if not retry else (max_retries if max_retries is not None else 2) + 1

        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await provider_instance.complete(
                    prompt=prompt_for_provider,
                    options=call_options,
                    meta=meta,
                )
                break
            except (LLMRateLimitError, LLMAPIError, LLMTimeoutError) as exc:
                last_exc = exc
                if not retry or attempt >= attempts or not self._is_retryable(exc):
                    self._log_failure(agent_id, selected_provider, call_options.model, exc, attempt)
                    raise
                backoff = self._compute_backoff(attempt)
                logger.warning(
                    "llm_call_retry",
                    agent_id=agent_id,
                    provider=selected_provider,
                    model=call_options.model,
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    backoff_s=backoff,
                    error=type(exc).__name__,
                    error_message=str(exc),
                )
                await asyncio.sleep(backoff)
            except LLMCallError as exc:
                self._log_failure(agent_id, selected_provider, call_options.model, exc, attempt)
                raise
            except Exception as exc:  # 兜底：未分类异常
                self._log_failure(agent_id, selected_provider, call_options.model, exc, attempt)
                raise LLMCallError(
                    message=f"Unexpected error during LLM call: {exc}",
                    details={
                        "agent_id": agent_id,
                        "provider": selected_provider,
                        "model": call_options.model,
                    },
                ) from exc
        else:  # pragma: no cover - 进入这里说明 break 没触发，理论上 raise 已抛
            assert last_exc is not None
            raise last_exc

        # 4) JSON 解析（如要求）
        parsed: dict | None = None
        if response_format == "json":
            try:
                parsed = self._parse_json(response.content)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "llm_call",
                    agent_id=agent_id,
                    provider=selected_provider,
                    model=response.model,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    total_tokens=response.total_tokens,
                    latency_ms=round(response.latency_ms, 2),
                    error="LLMParseError",
                    error_message=str(exc),
                )
                raise LLMParseError(
                    provider=selected_provider,
                    model=response.model,
                    raw_response=response.content,
                    parse_error=str(exc),
                ) from exc

        response.parsed = parsed

        # 5) 成功结构化日志
        logger.info(
            "llm_call",
            agent_id=agent_id,
            provider=response.provider or selected_provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            latency_ms=round(response.latency_ms, 2),
            response_format=response_format,
        )
        return response

    async def complete_with_messages(
        self,
        agent_id: str,
        messages: list[dict],
        options: LLMCallOptions,
        provider: str | None = None,
        trace_id: str = "",
    ) -> LLMResponse:
        """兼容方法：旧 API。"""
        return await self.complete(
            agent_id=agent_id,
            messages=messages,
            response_format=None,
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            model=options.model,
            provider=provider,
            trace_id=trace_id,
        )

    # ------------------------------------------------------------- helpers

    def _build_call_options(
        self,
        *,
        messages: list[dict] | None,
        prompt: str | None,
        system_prompt: str | None,
        options: LLMCallOptions | None,
        temperature: float | None,
        max_tokens: int | None,
        model: str | None,
    ) -> LLMCallOptions:
        if options is not None:
            # 兼容旧调用：拷贝并按需覆盖
            return LLMCallOptions(
                system_prompt=options.system_prompt,
                messages=options.messages or messages,
                temperature=temperature if temperature is not None else options.temperature,
                max_tokens=max_tokens if max_tokens is not None else options.max_tokens,
                model=model or options.model,
            )

        if messages is not None:
            return LLMCallOptions(
                system_prompt="",
                messages=messages,
                temperature=temperature if temperature is not None else 0.7,
                max_tokens=max_tokens,
                model=model,
            )

        # prompt + 可选 system_prompt 路径
        return LLMCallOptions(
            system_prompt=system_prompt or "",
            messages=None,
            temperature=temperature if temperature is not None else 0.7,
            max_tokens=max_tokens,
            model=model,
        )

    def _is_retryable(self, exc: Exception) -> bool:
        if isinstance(exc, LLMRateLimitError):
            return True
        if isinstance(exc, LLMTimeoutError):
            return True
        if isinstance(exc, LLMAPIError):
            status = (exc.details or {}).get("status_code")
            return isinstance(status, int) and status in _RETRYABLE_STATUS
        return False

    def _compute_backoff(self, attempt: int) -> float:
        # 1s, 2s, 4s 上限 8s
        return min(8.0, float(2 ** (attempt - 1)))

    def _log_failure(
        self,
        agent_id: str,
        provider: str,
        model: str | None,
        exc: Exception,
        attempt: int,
    ) -> None:
        logger.error(
            "llm_call",
            agent_id=agent_id,
            provider=provider,
            model=model or "auto",
            attempt=attempt,
            error=type(exc).__name__,
            error_message=str(exc),
        )

    @staticmethod
    def _parse_json(content: str) -> dict:
        """
        从 LLM 文本里抠出 JSON。

        兼容三种常见输出：
        1. 纯 JSON
        2. ```json ... ``` 围栏
        3. 任意围栏 ``` ... ```
        4. 头尾混入说明文字时退化到正则抽取首个 {...} 或 [...]
        """
        if content is None:
            raise ValueError("Empty content from LLM")
        text = content.strip()
        if not text:
            raise ValueError("Empty content from LLM")

        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise

    # ----------------------------------------------------------- accessors

    def get_available_providers(self) -> list[str]:
        return list(self._providers.keys())

    def is_provider_available(self, provider: str) -> bool:
        return provider in self._providers

    def get_default_provider(self) -> str:
        return self._default_provider

    def get_config(self) -> LLMConfig:
        return self.config

    def get_db_config(self) -> dict[str, dict]:
        return self._db_config.copy()

    def reload_config(self) -> None:
        self._load_db_config()
        self._init_providers()


# =============================================================================
# 全局单例
# =============================================================================

_llm_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    """获取 LLM Gateway 单例，延迟初始化。"""
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway


def reload_llm_gateway() -> LLMGateway:
    """重新加载 LLM Gateway（清除缓存，重新初始化）。"""
    global _llm_gateway
    _llm_gateway = LLMGateway()
    return _llm_gateway
