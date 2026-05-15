"""System configuration service."""

import json
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tables import SystemConfigModel


IMAGE_GENERATION_PROVIDER_PRESETS: list[dict[str, str]] = [
    {
        "provider_id": "dashscope",
        "name": "Alibaba DashScope / Wan",
        "default_model": "wan2.7-image",
        "default_base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
        "api_key_hint": "DASHSCOPE_API_KEY",
    },
    {
        "provider_id": "openai",
        "name": "OpenAI Images",
        "default_model": "gpt-image-1.5",
        "default_base_url": "https://api.openai.com/v1/images/generations",
        "api_key_hint": "OPENAI_API_KEY",
    },
    {
        "provider_id": "google_vertex",
        "name": "Google Vertex AI Imagen",
        "default_model": "imagen-4.0-generate-001",
        "default_base_url": "",
        "api_key_hint": "Google Cloud ADC or service account",
    },
    {
        "provider_id": "stability",
        "name": "Stability AI",
        "default_model": "stable-image-core",
        "default_base_url": "https://api.stability.ai/v2beta/stable-image/generate/core",
        "api_key_hint": "STABILITY_API_KEY",
    },
    {
        "provider_id": "volcengine",
        "name": "Volcengine Seedream",
        "default_model": "doubao-seedream-4-5-251128",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
        "api_key_hint": "LAS_API_KEY or Volcengine credentials",
    },
    {
        "provider_id": "custom",
        "name": "Custom / proxy",
        "default_model": "",
        "default_base_url": "",
        "api_key_hint": "Provider-specific API key",
    },
]


# Default configuration keys and their values
DEFAULT_CONFIGS: list[dict] = [
    # Database
    {
        "key": "database_url",
        "value": "sqlite+aiosqlite:///./hotclaw.db",
        "value_type": "string",
        "description": "数据库连接 URL",
        "category": "database",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": True,
    },
    # Redis
    {
        "key": "redis_url",
        "value": "redis://localhost:6379/0",
        "value_type": "string",
        "description": "Redis 连接 URL",
        "category": "redis",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": True,
    },
    # App Settings
    {
        "key": "app_env",
        "value": "development",
        "value_type": "string",
        "description": "运行环境：development / production",
        "category": "app",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "app_debug",
        "value": "true",
        "value_type": "boolean",
        "description": "调试模式",
        "category": "app",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "app_host",
        "value": "0.0.0.0",
        "value_type": "string",
        "description": "服务监听地址",
        "category": "app",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": True,
    },
    {
        "key": "app_port",
        "value": "8000",
        "value_type": "number",
        "description": "服务监听端口",
        "category": "app",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": True,
    },
    {
        "key": "ui_language",
        "value": "en",
        "value_type": "string",
        "description": "Global console UI language (en / zh-CN)",
        "category": "app",
        "is_sensitive": False,
        "is_system": False,
        "requires_restart": False,
    },
    # Image assets
    {
        "key": "image_generation_enabled",
        "value": "false",
        "value_type": "boolean",
        "description": "Enable AI image generation for draft preview image assets.",
        "category": "image_assets",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "image_generation_provider",
        "value": "dashscope",
        "value_type": "string",
        "description": "Provider used for AI image generation. This is independent from the default text LLM provider.",
        "category": "image_assets",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "image_generation_model",
        "value": "wan2.7-image",
        "value_type": "string",
        "description": "Default AI image generation model used by the future image asset pipeline.",
        "category": "image_assets",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "image_generation_api_key",
        "value": "",
        "value_type": "string",
        "description": "API key for the selected image generation provider.",
        "category": "image_assets",
        "is_sensitive": True,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "image_generation_base_url",
        "value": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
        "value_type": "string",
        "description": "Base URL or endpoint for the selected image generation provider.",
        "category": "image_assets",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "image_generation_provider_presets",
        "value": json.dumps(IMAGE_GENERATION_PROVIDER_PRESETS, ensure_ascii=False),
        "value_type": "json",
        "description": "Common image generation provider presets for the settings UI.",
        "category": "image_assets",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "image_search_provider",
        "value": "none",
        "value_type": "string",
        "description": "Optional external image search provider. Leave as none until a search API is wired.",
        "category": "image_assets",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    # MCP servers
    {
        "key": "enable_xiaohongshu_mcp",
        "value": "false",
        "value_type": "boolean",
        "description": "Enable the Xiaohongshu MCP publishing server for future Xiaohongshu workflows.",
        "category": "mcp",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": True,
    },
    {
        "key": "xiaohongshu_phone_number",
        "value": "",
        "value_type": "string",
        "description": "Phone number used by the Xiaohongshu MCP server login flow.",
        "category": "mcp",
        "is_sensitive": True,
        "is_system": True,
        "requires_restart": True,
    },
    {
        "key": "xiaohongshu_mcp_command",
        "value": "python",
        "value_type": "string",
        "description": "Command used to start the Xiaohongshu MCP server.",
        "category": "mcp",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": True,
    },
    {
        "key": "xiaohongshu_mcp_timeout_seconds",
        "value": "120",
        "value_type": "number",
        "description": "Timeout budget for Xiaohongshu MCP operations.",
        "category": "mcp",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "xiaohongshu_chromedriver_path",
        "value": "",
        "value_type": "string",
        "description": "Optional chromedriver path for the Xiaohongshu MCP server.",
        "category": "mcp",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": True,
    },
    # Log
    {
        "key": "log_level",
        "value": "INFO",
        "value_type": "string",
        "description": "日志级别：DEBUG / INFO / WARNING / ERROR",
        "category": "log",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    # Timeouts
    {
        "key": "agent_timeout",
        "value": "120",
        "value_type": "number",
        "description": "Agent 执行超时时间（秒）",
        "category": "timeout",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "skill_timeout",
        "value": "60",
        "value_type": "number",
        "description": "Skill 执行超时时间（秒）",
        "category": "timeout",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "llm_timeout",
        "value": "60",
        "value_type": "number",
        "description": "LLM 调用超时时间（秒）",
        "category": "timeout",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    # Publish Protection
    {
        "key": "global_publish_enabled",
        "value": "true",
        "value_type": "boolean",
        "description": "系统发布总开关（关闭后禁止所有自动发布）",
        "category": "publish",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
    {
        "key": "global_emergency_stop",
        "value": "false",
        "value_type": "boolean",
        "description": "紧急停止开关（启用后阻断所有发布）",
        "category": "publish",
        "is_sensitive": False,
        "is_system": True,
        "requires_restart": False,
    },
]

REFRESHABLE_DEFAULT_CONFIG_KEYS = {"image_generation_provider_presets"}


class SystemConfigService:
    """Service for managing system configurations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> list[SystemConfigModel]:
        """Get all configurations."""
        result = await self.db.execute(
            select(SystemConfigModel).order_by(SystemConfigModel.category, SystemConfigModel.key)
        )
        return list(result.scalars().all())

    async def get_by_key(self, key: str) -> SystemConfigModel | None:
        """Get a single configuration by key."""
        result = await self.db.execute(select(SystemConfigModel).where(SystemConfigModel.key == key))
        return result.scalar_one_or_none()

    async def get_value(self, key: str, default: str | None = None) -> str | None:
        """Get configuration value, returns default if not found."""
        config = await self.get_by_key(key)
        return config.value if config else default

    async def get_typed_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with type conversion."""
        config = await self.get_by_key(key)
        if not config:
            return default

        value = config.value
        if config.value_type == "boolean":
            return value.lower() in ("true", "1", "yes") if value else default
        elif config.value_type == "number":
            try:
                return int(value) if "." not in value else float(value)
            except (ValueError, TypeError):
                return default
        elif config.value_type == "json":
            import json
            try:
                return json.loads(value) if value else default
            except json.JSONDecodeError:
                return default
        return value

    async def set_value(self, key: str, value: str, value_type: str = "string") -> SystemConfigModel:
        """Set a configuration value (insert or update)."""
        config = await self.get_by_key(key)
        if config:
            config.value = value
            if value_type != config.value_type:
                config.value_type = value_type
        else:
            config = SystemConfigModel(
                key=key,
                value=value,
                value_type=value_type,
                category="general",
            )
            self.db.add(config)

        await self.db.flush()
        return config

    async def delete(self, key: str) -> bool:
        """Delete a configuration. Returns False if not found or is system config."""
        config = await self.get_by_key(key)
        if not config or config.is_system:
            return False
        await self.db.delete(config)
        return True

    async def get_by_category(self, category: str) -> list[SystemConfigModel]:
        """Get all configurations in a category."""
        result = await self.db.execute(
            select(SystemConfigModel)
            .where(SystemConfigModel.category == category)
            .order_by(SystemConfigModel.key)
        )
        return list(result.scalars().all())

    async def get_image_generation_config(self) -> dict[str, Any]:
        """Return the current image generation runtime configuration."""
        return {
            "provider": await self.get_typed_value("image_generation_provider", "dashscope"),
            "model": await self.get_typed_value("image_generation_model", "wan2.7-image"),
            "enabled": await self.get_typed_value("image_generation_enabled", False),
            "api_key": await self.get_typed_value("image_generation_api_key", ""),
            "base_url": await self.get_typed_value(
                "image_generation_base_url",
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
            ),
            "provider_presets": await self.get_typed_value(
                "image_generation_provider_presets",
                IMAGE_GENERATION_PROVIDER_PRESETS,
            ),
        }

    async def to_dict(self, mask_sensitive: bool = True) -> dict[str, Any]:
        """Convert all configs to a dictionary, optionally masking sensitive values."""
        configs = await self.get_all()
        result = {}
        for config in configs:
            value = config.value
            if mask_sensitive and config.is_sensitive and value:
                value = "***" + value[-4:] if len(value) > 4 else "****"
            result[config.key] = value
        return result


async def init_default_configs(db: AsyncSession) -> None:
    """Initialize default configurations if they don't exist."""
    service = SystemConfigService(db)

    for cfg in DEFAULT_CONFIGS:
        existing = await service.get_by_key(cfg["key"])
        if not existing:
            config = SystemConfigModel(**cfg)
            db.add(config)
        elif cfg["key"] in REFRESHABLE_DEFAULT_CONFIG_KEYS:
            existing.value = cfg["value"]
            existing.value_type = cfg["value_type"]
            existing.description = cfg["description"]
            existing.category = cfg["category"]
            existing.is_sensitive = cfg["is_sensitive"]
            existing.is_system = cfg["is_system"]
            existing.requires_restart = cfg["requires_restart"]

    await db.commit()
