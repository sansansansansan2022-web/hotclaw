"""
Application configuration loaded from environment variables.

【配置管理模块】
使用 Pydantic Settings 自动从环境变量加载配置。
配置来源优先级：数据库自定义配置 > .env 文件 > 代码默认值

面试点：
- Pydantic BaseSettings 自动读取 .env 文件
- __init__ 中计算派生属性的方法
- extra="ignore" 允许添加新字段而不破坏现有代码
"""

import os
import io
from pathlib import Path

# Load .env file first (with UTF-8 encoding for Windows compatibility)
# 【关键设计】在 Pydantic 加载前手动解析 .env 文件
# 这样 os.environ 会被提前填充，Pydantic 就能读取到这些值
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释行，解析 key=value 格式
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                # setdefault: 如果环境变量已存在则不覆盖
                normalized_key = key.strip()
                normalized_value = value.strip()
                existing_value = os.environ.get(normalized_key)
                os.environ[normalized_key] = (
                    existing_value.strip() if existing_value is not None else normalized_value
                )

from pydantic_settings import BaseSettings
from pydantic import Field


def _get_llm_config() -> tuple[str, str, str]:
    """
    Get LLM configuration based on default provider.

    【LLM 配置解析函数】
    根据 LLM_DEFAULT_PROVIDER 环境变量选择对应的 Provider，
    返回 (api_key, base_url, model) 三元组

    支持的 Provider：
    - deepseek: DeepSeek 系列模型（默认）
    - dashscope: 阿里云通义千问/Qwen
    - openai: OpenAI GPT 系列
    - compatible: 兼容 OpenAI 接口的其他模型（如本地部署）

    Returns:
        tuple[str, str, str]: (API密钥, API地址, 模型名称)
    """
    # 从环境变量读取默认 Provider，默认为 deepseek
    provider = os.getenv("LLM_DEFAULT_PROVIDER", "deepseek").lower()

    # 【配置字典】每个 Provider 的环境变量映射
    configs = {
        "dashscope": {
            "api_key": os.getenv("DASHSCOPE_API_KEY", ""),
            "base_url": os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            # DashScope 默认模型，擅长中文理解
            "model": os.getenv("DASHSCOPE_MODEL", "qwen-turbo"),
        },
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            # OpenAI 默认使用 GPT-4o-mini（性价比高）
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        },
        "compatible": {
            # 用于对接兼容 OpenAI 接口的本地模型服务
            "api_key": os.getenv("COMPATIBLE_API_KEY", ""),
            "base_url": os.getenv("COMPATIBLE_BASE_URL", "http://localhost:8000/v1"),
            "model": os.getenv("COMPATIBLE_MODEL", ""),
        },
        "deepseek": {
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            # DeepSeek Chat 模型，支持超长上下文
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        },
    }

    # 获取对应 Provider 配置，如果 Provider 不存在则回退到 deepseek
    cfg = configs.get(provider, configs["deepseek"])
    return cfg["api_key"], cfg["base_url"], cfg["model"]


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    【Pydantic Settings 配置类】
    所有字段都有默认值，确保应用能在最小配置下启动。
    Field() 的 description 用于文档化，不影响实际行为。

    面试点：Pydantic v2 的 model_config 配置
    - case_sensitive=False: 环境变量不区分大小写
    - extra="ignore": 忽略 .env 中未定义的字段，避免破坏性变更
    """

    # ========== Database 配置 ==========
    # SQLite 默认值方便本地开发，MySQL 用于生产环境
    # 格式：dialect+driver://username:password@host:port/database
    # aiosqlite = asyncio 版本的 SQLite 驱动
    database_url: str = Field(
        default="sqlite+aiosqlite:///./hotclaw.db",
        description="Database connection URL，支持 SQLite 和 MySQL",
    )

    # ========== Redis 配置（预留，当前未使用）==========
    # Redis 可用于：SSE 分布式订阅、任务队列、缓存
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for future caching/queue",
    )

    # ========== LLM 配置（运行时从 Provider 派生）==========
    # 这三个字段在 __init__ 中根据 Provider 自动填充
    llm_api_key: str = ""           # API 密钥
    llm_api_base_url: str = "https://api.deepseek.com"  # API 基础地址
    llm_model_name: str = "deepseek-chat"  # 模型名称

    # ========== 应用配置 ==========
    app_env: str = Field(default="development", description="运行环境")
    app_debug: bool = Field(default=False, description="调试模式开关")
    app_host: str = Field(default="0.0.0.0", description="监听地址")
    app_port: int = Field(default=8000, description="监听端口")

    # ========== 日志配置 ==========
    log_level: str = Field(default="INFO", description="日志级别")

    # ========== 超时配置（秒）==========
    # agent_timeout: 单个智能体执行超时（正文生成可能需要较长时间）
    agent_timeout: int = Field(default=120, description="智能体执行超时（秒）")
    # skill_timeout: 单个技能执行超时
    skill_timeout: int = Field(default=60, description="技能执行超时（秒）")
    # llm_timeout: LLM API 调用超时
    llm_timeout: int = Field(default=60, description="LLM API 调用超时（秒）")

    enable_github_skill: bool = Field(default=False, description="Enable GitHub research skill")
    enable_scholar_skill: bool = Field(default=False, description="Enable scholar research skill")
    skill_cache_ttl_seconds: int = Field(default=21600, description="Skill cache TTL in seconds")

    github_token: str = Field(default="", description="GitHub API token")
    github_api_mode: str = Field(default="rest", description="GitHub API mode")
    github_api_base_url: str = Field(default="https://api.github.com", description="GitHub API base URL")
    github_skill_timeout_seconds: int = Field(default=20, description="GitHub skill timeout in seconds")

    scholar_provider: str = Field(default="", description="Scholar provider strategy")
    scholar_provider_api_key: str = Field(default="", description="Scholar provider API key")
    scholar_skill_timeout_seconds: int = Field(default=20, description="Scholar skill timeout in seconds")

    openalex_base_url: str = Field(default="https://api.openalex.org", description="OpenAlex API base URL")
    openalex_api_key: str = Field(default="", description="OpenAlex API key")
    openalex_mailto: str = Field(default="", description="OpenAlex polite pool email")

    crossref_base_url: str = Field(default="https://api.crossref.org", description="Crossref API base URL")
    crossref_api_key: str = Field(default="", description="Crossref API key")
    crossref_mailto: str = Field(default="", description="Crossref polite pool email")

    semantic_scholar_base_url: str = Field(
        default="https://api.semanticscholar.org",
        description="Semantic Scholar API base URL",
    )
    semantic_scholar_api_key: str = Field(default="", description="Semantic Scholar API key")

    model_config = {
        # 环境变量不区分大小写（LLM_API_KEY = llm_api_key）
        "case_sensitive": False,
        # 忽略 .env 中未在类中定义的字段
        "extra": "ignore",
    }

    def __init__(self, **kwargs):
        """
        初始化时自动计算 LLM 配置。

        【关键设计】在 __init__ 中调用 _get_llm_config()
        这样 llm_api_key/base_url/model_name 会根据选定的 Provider 自动填充
        """
        super().__init__(**kwargs)
        # Load provider-specific LLM config
        api_key, base_url, model = _get_llm_config()
        self.llm_api_key = api_key
        self.llm_api_base_url = base_url
        self.llm_model_name = model


# 【单例模式】全局配置实例
# 整个应用导入 settings 时自动初始化，所有模块共享同一份配置
settings = Settings()
