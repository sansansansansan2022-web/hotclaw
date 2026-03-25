"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database
    # Production: postgresql+asyncpg://user:pass@host/db
    # Development: sqlite+aiosqlite:///./hotclaw.db
    database_url: str = Field(
        default="sqlite+aiosqlite:///./hotclaw.db",
        description="Database connection URL (SQLite for dev, PostgreSQL for prod)",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # LLM
    llm_api_key: str = Field(default="", description="LLM API key")
    llm_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="LLM API base URL",
    )
    llm_model_name: str = Field(
        default="gpt-4o-mini",
        description="Default LLM model name",
    )

    # App
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=False)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)

    # Log
    log_level: str = Field(default="INFO")

    # Timeouts (seconds)
    agent_timeout: int = Field(default=120)
    skill_timeout: int = Field(default=60)
    llm_timeout: int = Field(default=60)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # 允许额外字段，避免与 LLMConfig 配置冲突
    }


settings = Settings()
