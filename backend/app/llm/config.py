"""LLM Provider 配置管理。

统一管理所有 LLM Provider 的配置，支持从环境变量加载。
"""

from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    """LLM Provider 统一配置"""

    # 默认 Provider
    default_provider: str = Field(
        default="dashscope",
        description="默认 LLM Provider: dashscope, openai, compatible, deepseek",
    )

    # DashScope 配置
    dashscope_api_key: str = Field(
        default="",
        description="阿里云 DashScope API Key",
    )
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="DashScope API Base URL",
    )
    dashscope_model: str = Field(
        default="qwen3.5-plus",
        description="默认 DashScope 模型",
    )

    # OpenAI 配置
    openai_api_key: str = Field(
        default="",
        description="OpenAI API Key",
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API Base URL",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="默认 OpenAI 模型",
    )

    # OpenAI Compatible 配置（vLLM/Ollama 等）
    compatible_api_key: str = Field(
        default="",
        description="兼容模式 API Key",
    )
    compatible_base_url: str = Field(
        default="http://localhost:8000/v1",
        description="兼容模式 Base URL",
    )
    compatible_model: str = Field(
        default="",
        description="默认兼容模式模型",
    )

    # DeepSeek 配置
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API Key",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API Base URL",
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="默认 DeepSeek 模型",
    )

    # 通用配置
    timeout: int = Field(
        default=60,
        description="LLM 调用超时（秒）",
    )
    max_retries: int = Field(
        default=2,
        description="最大重试次数",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # 允许额外字段，避免与其他配置冲突
    }

    @field_validator("default_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        valid = {"dashscope", "openai", "compatible", "deepseek"}
        if v and v not in valid:
            raise ValueError(f"default_provider must be one of {valid}")
        return v

    def get_default_model(self, provider: str) -> str:
        """
        获取指定 provider 的默认模型

        Args:
            provider: Provider 名称

        Returns:
            默认模型名
        """
        return {
            "dashscope": self.dashscope_model,
            "openai": self.openai_model,
            "compatible": self.compatible_model,
            "deepseek": self.deepseek_model,
        }.get(provider, "")

    def get_provider_config(self, provider: str) -> dict:
        """
        获取指定 provider 的配置

        Args:
            provider: Provider 名称

        Returns:
            配置字典
        """
        configs = {
            "dashscope": {
                "api_key": self.dashscope_api_key,
                "base_url": self.dashscope_base_url,
                "model": self.dashscope_model,
            },
            "openai": {
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url,
                "model": self.openai_model,
            },
            "compatible": {
                "api_key": self.compatible_api_key,
                "base_url": self.compatible_base_url,
                "model": self.compatible_model,
            },
            "deepseek": {
                "api_key": self.deepseek_api_key,
                "base_url": self.deepseek_base_url,
                "model": self.deepseek_model,
            },
        }
        return configs.get(provider, {})

    def is_provider_configured(self, provider: str) -> bool:
        """
        检查 provider 是否已配置

        Args:
            provider: Provider 名称

        Returns:
            是否已配置
        """
        config = self.get_provider_config(provider)
        api_key = config.get("api_key", "")
        return bool(api_key)


# 全局配置单例
_llm_config: LLMConfig | None = None


@lru_cache
def get_llm_config() -> LLMConfig:
    """获取 LLM 配置单例（带缓存）"""
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig()
    return _llm_config


def reload_llm_config() -> LLMConfig:
    """重新加载 LLM 配置（清除缓存）"""
    global _llm_config
    _llm_config = None
    return get_llm_config()
