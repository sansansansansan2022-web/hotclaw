"""System configuration service."""

from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tables import SystemConfigModel


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
]


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

    await db.commit()
