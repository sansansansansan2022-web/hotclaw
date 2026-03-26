"""LLM Gateway - 统一 LLM 调用入口。

提供统一的 LLM 调用接口，自动处理：
- Provider 路由和选择（支持数据库动态配置）
- 请求日志和追踪
- 错误处理和异常转换
- Provider 初始化和生命周期管理
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
        """从数据库加载用户配置的 Provider"""
        try:
            import asyncio
            from sqlalchemy import select
            from app.db.session import async_session_factory
            from app.models.tables import LLMProviderModel

            # 同步方式获取数据库配置
            async def _load():
                async with AsyncSessionLocal() as session:
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

            # 运行异步加载
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在事件循环中，使用创建任务的方式
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _load())
                    self._db_config, default_from_db = future.result()
            else:
                self._db_config, default_from_db = asyncio.run(_load())

            # 如果数据库有默认 Provider，覆盖 .env 配置
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
        """根据配置初始化所有可用的 Provider"""
        initialized = []

        # 获取 Provider 配置（优先数据库，其次 .env）
        def get_provider_config(provider_id: str) -> dict | None:
            if provider_id in self._db_config:
                return self._db_config[provider_id]
            # 回退到 .env 配置
            return self.config.get_provider_config(provider_id)

        # 初始化 DashScope
        dashscope_config = get_provider_config("dashscope")
        if dashscope_config and dashscope_config.get("api_key"):
            try:
                self._providers["dashscope"] = DashScopeProvider(
                    api_key=dashscope_config["api_key"],
                    base_url=dashscope_config.get("base_url") or self.config.dashscope_base_url,
                    timeout=dashscope_config.get("timeout") or self.config.timeout,
                )
                initialized.append("dashscope")
            except LLMConfigurationError as e:
                logger.warning(
                    "llm_provider_init_skipped",
                    provider="dashscope",
                    reason=str(e),
                )

        # 初始化 OpenAI
        openai_config = get_provider_config("openai")
        if openai_config and openai_config.get("api_key"):
            try:
                self._providers["openai"] = OpenAIProvider(
                    api_key=openai_config["api_key"],
                    base_url=openai_config.get("base_url") or self.config.openai_base_url,
                    timeout=openai_config.get("timeout") or self.config.timeout,
                )
                initialized.append("openai")
            except LLMConfigurationError as e:
                logger.warning(
                    "llm_provider_init_skipped",
                    provider="openai",
                    reason=str(e),
                )

        # 初始化 DeepSeek
        deepseek_config = get_provider_config("deepseek")
        if deepseek_config and deepseek_config.get("api_key"):
            try:
                self._providers["deepseek"] = DeepSeekProvider(
                    api_key=deepseek_config["api_key"],
                    base_url=deepseek_config.get("base_url") or "https://api.deepseek.com",
                    timeout=deepseek_config.get("timeout") or self.config.timeout,
                )
                initialized.append("deepseek")
            except LLMConfigurationError as e:
                logger.warning(
                    "llm_provider_init_skipped",
                    provider="deepseek",
                    reason=str(e),
                )

        # 初始化 OpenAI Compatible
        compatible_config = get_provider_config("compatible")
        if compatible_config and compatible_config.get("base_url"):
            try:
                self._providers["compatible"] = OpenAICompatibleProvider(
                    api_key=compatible_config.get("api_key") or None,
                    base_url=compatible_config["base_url"],
                    timeout=compatible_config.get("timeout") or self.config.timeout,
                )
                initialized.append("compatible")
            except LLMConfigurationError as e:
                logger.warning(
                    "llm_provider_init_skipped",
                    provider="compatible",
                    reason=str(e),
                )

        # 初始化 Zhipu (智谱)
        zhipu_config = get_provider_config("zhipu")
        if zhipu_config and zhipu_config.get("api_key"):
            try:
                # Zhipu 也使用 OpenAI 兼容接口
                self._providers["zhipu"] = OpenAICompatibleProvider(
                    api_key=zhipu_config["api_key"],
                    base_url=zhipu_config.get("base_url") or "https://open.bigmodel.cn/api/paas/v4",
                    timeout=zhipu_config.get("timeout") or self.config.timeout,
                )
                initialized.append("zhipu")
            except LLMConfigurationError as e:
                logger.warning(
                    "llm_provider_init_skipped",
                    provider="zhipu",
                    reason=str(e),
                )

        if not initialized:
            logger.warning(
                "no_llm_providers_initialized",
                message="No LLM providers configured. Check API keys in database or .env",
            )
        else:
            logger.info(
                "llm_providers_initialized",
                providers=initialized,
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

        Args:
            agent_id: 调用方 agent ID（用于日志和追踪）
            prompt: 用户输入提示词
            options: 调用选项
            provider: 可选，指定 provider（默认使用配置中的 default_provider）
            trace_id: 可选，追踪 ID

        Returns:
            LLMResponse

        Raises:
            LLMCallError: 调用失败
            LLMConfigurationError: Provider 未配置
        """
        selected_provider = provider or self._default_provider

        # 获取默认模型（优先数据库配置）
        model = options.model
        if not model:
            if selected_provider in self._db_config:
                model = self._db_config[selected_provider].get("default_model")
            if not model:
                model = self.config.get_default_model(selected_provider)

        # 构建调用元信息
        meta = LLMCallMeta(
            agent_id=agent_id,
            trace_id=trace_id,
        )

        # 日志：调用开始
        logger.info(
            "llm_call_start",
            agent_id=agent_id,
            trace_id=trace_id,
            provider=selected_provider,
            model=model or "auto",
            system_prompt_length=len(options.system_prompt),
            prompt_length=len(prompt),
            temperature=options.temperature,
            max_tokens=options.max_tokens,
        )

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
                agent_id=agent_id,
                trace_id=trace_id,
                provider=selected_provider,
                error_type="LLMConfigurationError",
                error_message=error_msg,
            )
            raise LLMConfigurationError(
                provider=selected_provider,
                message=error_msg,
            )

        try:
            # 执行调用
            response = await provider_instance.complete(
                prompt=prompt,
                options=options,
                meta=meta,
            )

            # 日志：调用成功
            logger.info(
                "llm_call_success",
                agent_id=agent_id,
                trace_id=trace_id,
                provider=selected_provider,
                model=response.model,
                latency_ms=round(response.latency_ms, 2),
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
            )

            return response

        except LLMCallError:
            # 已经是标准异常，直接重新抛出（日志已在 Provider 中记录）
            raise

        except Exception as e:
            # 未预期的异常
            logger.error(
                "llm_call_failed",
                agent_id=agent_id,
                trace_id=trace_id,
                provider=selected_provider,
                model=model or "auto",
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True,  # 记录完整堆栈
            )
            raise LLMCallError(
                message=f"Unexpected error during LLM call: {str(e)}",
                details={
                    "agent_id": agent_id,
                    "provider": selected_provider,
                    "model": model,
                    "original_error": type(e).__name__,
                },
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

        Args:
            agent_id: 调用方 agent ID
            messages: 预构建的消息列表
            options: 调用选项（注意：system_prompt 会被忽略）
            provider: 可选，指定 provider
            trace_id: 可选，追踪 ID

        Returns:
            LLMResponse
        """
        # 创建新的 options，覆盖 messages
        call_options = LLMCallOptions(
            system_prompt="",  # 忽略，使用 messages
            messages=messages,
            temperature=options.temperature,
            max_tokens=options.max_tokens,
            model=options.model,
        )

        # 构建一个空 prompt（messages 已包含所有内容）
        return await self.complete(
            agent_id=agent_id,
            prompt="",  # messages 已包含用户消息
            options=call_options,
            provider=provider,
            trace_id=trace_id,
        )

    def get_available_providers(self) -> list[str]:
        """获取已初始化的 Provider 列表"""
        return list(self._providers.keys())

    def is_provider_available(self, provider: str) -> bool:
        """检查 Provider 是否可用"""
        return provider in self._providers

    def get_default_provider(self) -> str:
        """获取默认 Provider"""
        return self._default_provider

    def get_config(self) -> LLMConfig:
        """获取 .env 配置对象"""
        return self.config

    def get_db_config(self) -> dict[str, dict]:
        """获取数据库配置"""
        return self._db_config.copy()

    def reload_config(self) -> None:
        """重新加载配置（数据库 + .env）"""
        self._load_db_config()
        self._init_providers()


# 全局单例实例
_llm_gateway: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    """获取 LLM Gateway 单例"""
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway


def reload_llm_gateway() -> LLMGateway:
    """重新加载 LLM Gateway（清除缓存）"""
    global _llm_gateway
    _llm_gateway = LLMGateway()
    return _llm_gateway
