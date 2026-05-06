"""System configuration API routes."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.system_config_service import SystemConfigService, init_default_configs


router = APIRouter(prefix="/system-configs", tags=["系统配置"])


class ConfigItem(BaseModel):
    """Single configuration item."""
    key: str
    value: str | None
    value_type: str = "string"
    description: str | None = None
    category: str = "general"
    is_sensitive: bool = False
    is_system: bool = False
    requires_restart: bool = False


class ConfigUpdate(BaseModel):
    """Update configuration request."""
    value: str
    value_type: str = Field(default="string", pattern="^(string|number|boolean|json)$")


class ConfigCreate(BaseModel):
    """Create new configuration request."""
    key: str = Field(min_length=1, max_length=100)
    value: str | None = None
    value_type: str = Field(default="string", pattern="^(string|number|boolean|json)$")
    description: str | None = None
    category: str = Field(default="general", max_length=32)
    is_sensitive: bool = False


# Dependency
async def get_config_service(db: AsyncSession = Depends(get_db)) -> SystemConfigService:
    return SystemConfigService(db)


@router.get("", response_model=list[ConfigItem])
async def list_configs(
    category: str | None = Query(None, description="按分类筛选"),
    service: SystemConfigService = Depends(get_config_service),
):
    """List all configurations."""
    if category:
        configs = await service.get_by_category(category)
    else:
        configs = await service.get_all()
    return configs


@router.get("/all", response_model=dict[str, Any])
async def get_all_configs_dict(
    service: SystemConfigService = Depends(get_config_service),
):
    """Get all configurations as a key-value dictionary (sensitive values masked)."""
    return await service.to_dict(mask_sensitive=True)


@router.get("/{key}", response_model=ConfigItem)
async def get_config(
    key: str,
    service: SystemConfigService = Depends(get_config_service),
):
    """Get a single configuration by key."""
    config = await service.get_by_key(key)
    if not config:
        raise HTTPException(status_code=404, detail=f"配置项 '{key}' 不存在")
    return config


@router.get("/{key}/value")
async def get_config_value(
    key: str,
    default: str | None = Query(None, description="默认值"),
    service: SystemConfigService = Depends(get_config_service),
):
    """Get configuration value (auto-type converted)."""
    value = await service.get_typed_value(key, default)
    if value is None and default is None:
        config = await service.get_by_key(key)
        if not config:
            raise HTTPException(status_code=404, detail=f"配置项 '{key}' 不存在")
    return {"key": key, "value": value}


@router.post("", response_model=ConfigItem, status_code=201)
async def create_config(
    data: ConfigCreate,
    service: SystemConfigService = Depends(get_config_service),
):
    """Create a new configuration."""
    existing = await service.get_by_key(data.key)
    if existing:
        raise HTTPException(status_code=400, detail=f"配置项 '{data.key}' 已存在")

    config = await service.set_value(data.key, data.value or "", data.value_type)
    await service.db.commit()

    # Update additional fields
    config.description = data.description
    config.category = data.category
    config.is_sensitive = data.is_sensitive
    await service.db.commit()

    return config


@router.put("/{key}", response_model=ConfigItem)
async def update_config(
    key: str,
    data: ConfigUpdate,
    service: SystemConfigService = Depends(get_config_service),
):
    """Update a configuration value."""
    config = await service.get_by_key(key)
    if not config:
        raise HTTPException(status_code=404, detail=f"配置项 '{key}' 不存在")

    config.value = data.value
    if data.value_type:
        config.value_type = data.value_type

    await service.db.commit()
    return config


@router.delete("/{key}", status_code=204)
async def delete_config(
    key: str,
    service: SystemConfigService = Depends(get_config_service),
):
    """Delete a configuration (system configs cannot be deleted)."""
    success = await service.delete(key)
    if not success:
        config = await service.get_by_key(key)
        if not config:
            raise HTTPException(status_code=404, detail=f"配置项 '{key}' 不存在")
        raise HTTPException(status_code=400, detail="系统级配置不能删除")
    await service.db.commit()


@router.post("/init", status_code=201)
async def initialize_default_configs(
    db: AsyncSession = Depends(get_db),
):
    """Initialize default configurations (idempotent)."""
    await init_default_configs(db)
    return {"message": "默认配置初始化完成"}
