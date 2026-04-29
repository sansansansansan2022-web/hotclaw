"""System configuration API routes."""

import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.system_config_service import (
    IMAGE_GENERATION_PROVIDER_PRESETS,
    SystemConfigService,
    init_default_configs,
)
from app.services.image_generation_service import SUPPORTED_IMAGE_GENERATION_PROVIDERS


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


class ImageGenerationConnectionTestRequest(BaseModel):
    """Image generation provider connection test request."""

    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class ConnectionTestResponse(BaseModel):
    """Generic connection test response."""

    success: bool
    latency_ms: float | None = None
    response_preview: str | None = None
    error_message: str | None = None


# Dependency
async def get_config_service(db: AsyncSession = Depends(get_db)) -> SystemConfigService:
    return SystemConfigService(db)


def _get_image_provider_preset(provider_id: str) -> dict[str, str] | None:
    return next((preset for preset in IMAGE_GENERATION_PROVIDER_PRESETS if preset["provider_id"] == provider_id), None)


def _derive_models_endpoint(base_url: str) -> str | None:
    normalized = base_url.rstrip("/")
    if "/images/" in normalized:
        return f"{normalized.split('/images/', 1)[0]}/models"
    if normalized.endswith("/images"):
        return f"{normalized.rsplit('/images', 1)[0]}/models"
    if normalized.endswith("/v1") or normalized.endswith("/v1beta") or normalized.endswith("/v1beta1"):
        return f"{normalized}/models"
    if normalized.endswith("/api/v3") or normalized.endswith("/api/v2beta"):
        return f"{normalized}/models"
    return None


def _extract_http_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message[:500]
        if isinstance(error, str) and error.strip():
            return error[:500]

        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail[:500]

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message[:500]

    text = response.text.strip()
    return text[:500] if text else f"HTTP {response.status_code}"


async def _run_image_connection_probe(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
) -> ConnectionTestResponse:
    provider = provider.strip().lower()
    if provider not in SUPPORTED_IMAGE_GENERATION_PROVIDERS:
        return ConnectionTestResponse(
            success=False,
            error_message=f"Provider '{provider}' is listed for configuration but image generation is not wired yet.",
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-HotClaw-Connection-Test": "1",
    }
    start_time = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            if provider in {"openai", "volcengine", "custom"}:
                models_url = _derive_models_endpoint(base_url)
                if models_url:
                    response = await client.get(models_url, headers=headers)
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    if response.status_code >= 400:
                        return ConnectionTestResponse(
                            success=False,
                            latency_ms=latency_ms,
                            error_message=_extract_http_error_message(response),
                        )

                    preview = "Connection test succeeded."
                    try:
                        payload = response.json()
                    except ValueError:
                        payload = {}

                    model_ids = []
                    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                        model_ids = [
                            item.get("id")
                            for item in payload["data"]
                            if isinstance(item, dict) and isinstance(item.get("id"), str)
                        ]

                    if model and model_ids and model not in model_ids:
                        return ConnectionTestResponse(
                            success=False,
                            latency_ms=latency_ms,
                            error_message=f"Model '{model}' is not available on this endpoint.",
                        )

                    if model and model_ids:
                        preview = f"Connection test succeeded. Model '{model}' is available."
                    elif model:
                        preview = f"Connection test succeeded. Endpoint reachable for model '{model}'."

                    return ConnectionTestResponse(
                        success=True,
                        latency_ms=latency_ms,
                        response_preview=preview,
                    )

            response = await client.post(
                base_url,
                headers=headers,
                json={
                    "model": model,
                    "prompt": "connection-test",
                    "input": {"prompt": "connection-test"},
                    "connection_test": True,
                },
            )
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            if response.status_code in {200, 201, 202}:
                return ConnectionTestResponse(
                    success=True,
                    latency_ms=latency_ms,
                    response_preview="Connection test succeeded.",
                )

            return ConnectionTestResponse(
                success=False,
                latency_ms=latency_ms,
                error_message=_extract_http_error_message(response),
            )
    except httpx.TimeoutException:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ConnectionTestResponse(success=False, latency_ms=latency_ms, error_message="Connection timed out")
    except httpx.HTTPError as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ConnectionTestResponse(success=False, latency_ms=latency_ms, error_message=str(exc)[:500])


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


@router.post("/image-generation/test", response_model=ConnectionTestResponse)
async def test_image_generation_connection(
    data: ImageGenerationConnectionTestRequest,
    service: SystemConfigService = Depends(get_config_service),
):
    """Test image generation provider connectivity."""

    current_config = await service.get_image_generation_config()
    provider = (data.provider or current_config.get("provider") or "dashscope").strip()
    model = (data.model or current_config.get("model") or "").strip()
    api_key = (data.api_key or current_config.get("api_key") or "").strip()

    preset = _get_image_provider_preset(provider)
    default_base_url = preset["default_base_url"] if preset else ""
    base_url = (data.base_url or current_config.get("base_url") or default_base_url or "").strip()

    if not api_key:
        return ConnectionTestResponse(success=False, error_message="API Key is required")

    if not base_url:
        return ConnectionTestResponse(success=False, error_message="Base URL is required")

    if not model:
        return ConnectionTestResponse(success=False, error_message="Model is required")

    return await _run_image_connection_probe(provider=provider, model=model, api_key=api_key, base_url=base_url)


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
