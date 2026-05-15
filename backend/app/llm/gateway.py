"""
LLM Gateway - 统一 LLM 调用入口。

【LLM 网关】
提供统一的 LLM 调用接口，是整个系统的"大模型入口"。
采用 Facade 门面模式，对外隐藏多 Provider 的复杂性。

核心功能：
- Provider 路由：根据 agent_id 选择合适的 LLM Provider
- 配置优先级：数据库自定义配置 > .env 环境变量
- 请求日志：每次调用记录完整的调用元信息
- 错误转换：将 Provider 异常转换为统一的 LLMCallError

面试点：
- Facade 门面模式
- 配置优先级设计
- LLM 调用最佳实践（超时、重试、JSON 输出解析）
- 多 Provider 架构
"""

from typing import Any

from app.core.logger import get_logger
from app.llm.base import LLMProvider, LLMResponse, LLMCallOptions, LLMCallMeta
from app.llm.config import LLMConfig, get_llm_config
from app.llm.exceptions import LLMCallError, LLMConfigurationError
from app.llm.providers.dashscope import DashScopeProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.compatible import OpenAICompatibleProvider
from app.llm.providers.deepseek import DeepSeekProvider

logger = get_logger(__name__)


class LLMGateway:
    """
    统一 LLM 网关门面

    支持两种配置来源：
    1. 数据库（优先级高）：用户在前端配置的 API Key
    2. .env 文件（备用）：传统的环境变量配置

    使用示例:
        gateway = LLMGateway()
        response = await gateway.complete(
            agent_id="profile_agent",
            prompt="解析以下账号定位：职场成长号",
            options=LLMCallOptions(system_prompt="你是一位专业的..."),
        )
        print(response.content)
    """

    def __init__(self, config: LLMConfig | None = None, use_db_config: bool = True):
        """
        初始化 LLM Gateway

        Args:
            config: 可选的配置对象，默认使用全局 .env 配置
            use_db_config: 是否从数据库加载用户配置（默认 True）
        """
        self.config = config or get_llm_config()
        self._providers: dict[str, LLMProvider] = {}
        self._db_config: dict[str, dict] = {}
        self._default_provider: str = self.config.default_provider

        if use_db_config:
            self._load_db_config()

        self._init_providers()

    def _load_db_config(self) -> None:
        """
        从数据库加载用户配置的 Provider。

        【配置优先级】
        数据库配置 > .env 配置
        这样用户可以在前端动态配置 API Key，
        而无需重启服务器或修改环境变量。
        """
        try:
            import asyncio
            from sqlalchemy import select
            from app.db.session import async_session_factory
            from app.models.tables import LLMProviderModel

            async def _load():
                async with async_session_factory() as session:
                    result = await session.execute(
                        select(LLMProviderModel).where(
                            LLMProviderModel.is_enabled == True
                        )
                    )
                    providers = result.scalars().all()

                    db_config = {}
                    default_provider = None

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

                    return db_config, default_provider

            # 处理异步加载（可能在事件循环中或外调用）
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                self._db_config, default_from_db = pool.submit(asyncio.run, _load()).result()

            # 覆盖默认 Provider
            if default_from_db:
                self._default_provider = default_from_db

            if self._db_config:
                logger.info(
                    "llm_db_config_loaded",
                    providers=list(self._db_config.keys()),
                    default_provider=self._default_provider,
                )

        except Exception as e:
            logger.warning(
                "llm_db_config_load_failed",
                error=str(e),
                message="Will use .env config instead",
            )
            self._db_config = {}

    def _init_providers(self) -> None:
        """
        根据配置初始化所有可用的 Provider。

        【Provider 初始化策略】
        只初始化有有效 API Key 的 Provider。
        如果某个 Provider 没有配置，优雅地跳过并记录警告。
        """
        def get_provider_config(provider_id: str) -> dict | None:
            # 优先数据库配置，回退到 .env
            if provider_id in self._db_config:
                return self._db_config[provider_id]
            return self.config.get_provider_config(provider_id)

        # 初始化 DashScope（阿里云通义千问）
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

        # 初始化 OpenAI
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

        # 初始化 DeepSeek
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

        # 初始化 OpenAI Compatible（兼容接口）
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

        # 初始化 Zhipu（智谱）
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

        # 初始化 Xiaomi MiMo（OpenAI Compatible）
        xiaomi_config = get_provider_config("xiaomi")
        if xiaomi_config and xiaomi_config.get("api_key"):
            try:
                self._providers["xiaomi"] = OpenAICompatibleProvider(
                    api_key=xiaomi_config["api_key"],
                    base_url=xiaomi_config.get("base_url") or "https://api.mimo-v2.com/v1",
                    timeout=xiaomi_config.get("timeout") or self.config.timeout,
                    provider_id="xiaomi",
                )
                logger.info("llm_provider_initialized", provider="xiaomi")
            except LLMConfigurationError as e:
                logger.warning("llm_provider_init_skipped", provider="xiaomi", reason=str(e))

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

    async def complete(
        self,
        agent_id: str,
        prompt: str,
        options: LLMCallOptions,
        provider: str | None = None,
        trace_id: str = "",
    ) -> LLMResponse:
        """
        执行 LLM 补全调用

        【核心方法】智能体调用 LLM 的入口

        Args:
            agent_id: 调用方 agent ID（用于日志和追踪）
            prompt: 用户输入提示词
            options: 调用选项（system_prompt, temperature, max_tokens 等）
            provider: 可选，指定 provider（默认使用配置的 default_provider）
            trace_id: 可选，追踪 ID（用于日志关联）

        Returns:
            LLMResponse: 包含 content, model, latency_ms, token 使用量

        Raises:
            LLMCallError: 调用失败
            LLMConfigurationError: Provider 未配置
        """
        # 选择 Provider（优先参数，次优先数据库配置，最后用默认）
        selected_provider = provider or self._default_provider

        # 选择模型（优先 options，次优先数据库配置，最后用默认）
        model = options.model
        if not model:
            if selected_provider in self._db_config:
                model = self._db_config[selected_provider].get("default_model")
            if not model:
                model = self.config.get_default_model(selected_provider)

        # 构建调用元信息
        meta = LLMCallMeta(agent_id=agent_id, trace_id=trace_id)

        # 获取 Provider 实例
        provider_instance = self._providers.get(selected_provider)
        if not provider_instance:
            available = list(self._providers.keys())
            error_msg = (
                f"Provider '{selected_provider}' not available. "
                f"Available providers: {available}"
            )
            logger.error(
                "llm_call_failed",
                agent_id=agent_id, provider=selected_provider,
                error_type="LLMConfigurationError", error_message=error_msg,
            )
            raise LLMConfigurationError(provider=selected_provider, message=error_msg)

        try:
            # 执行调用
            response = await provider_instance.complete(prompt=prompt, options=options, meta=meta)

            # 记录成功日志
            logger.info(
                "llm_call_success",
                agent_id=agent_id, provider=selected_provider, model=response.model,
                latency_ms=round(response.latency_ms, 2),
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
            )
            return response

        except LLMCallError:
            raise  # Provider 异常已记录日志，直接重新抛出
        except Exception as e:
            logger.error(
                "llm_call_failed",
                agent_id=agent_id, provider=selected_provider, model=model or "auto",
                error_type=type(e).__name__, error_message=str(e), exc_info=True,
            )
            raise LLMCallError(
                message=f"Unexpected error during LLM call: {str(e)}",
                details={"agent_id": agent_id, "provider": selected_provider, "model": model},
            ) from e

    async def complete_with_messages(
        self,
        agent_id: str,
        messages: list[dict],
        options: LLMCallOptions,
        provider: str | None = None,
        trace_id: str = "",
    ) -> LLMResponse:
        """
        使用预构建的消息列表执行 LLM 调用

        【多轮对话方法】
        与 complete() 的区别：messages 是完整的对话历史，
        包含 system/user/assistant 消息，适合复杂对话场景。
        """
        call_options = LLMCallOptions(
            system_prompt="",  # 忽略，使用 messages 中的内容
            messages=messages,
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            model=options.model,
        )
        return await self.complete(
            agent_id=agent_id, prompt="",  # messages 已包含所有内容
            options=call_options, provider=provider, trace_id=trace_id,
        )

    def get_available_providers(self) -> list[str]:
        """获取已初始化的 Provider 列表。"""
        return list(self._providers.keys())

    def is_provider_available(self, provider: str) -> bool:
        """检查 Provider 是否可用。"""
        return provider in self._providers

    def get_default_provider(self) -> str:
        """获取默认 Provider。"""
        return self._default_provider

    def get_config(self) -> LLMConfig:
        """获取 .env 配置对象。"""
        return self.config

    def get_db_config(self) -> dict[str, dict]:
        """获取数据库配置。"""
        return self._db_config.copy()

    def reload_config(self) -> None:
        """
        重新加载配置。

        管理员在数据库修改 LLM 配置后调用，
        重新初始化所有 Provider。
        """
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
