"""Configuration API routes for hot-reload support."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/config", tags=["config"])


class ConfigReloadResponse(BaseModel):
    code: int
    message: str
    data: dict[str, Any] | None = None


class ConfigValueResponse(BaseModel):
    code: int
    message: str
    data: dict[str, Any]


@router.get("", response_model=ConfigValueResponse)
async def get_config() -> ConfigValueResponse:
    """Get current configuration values (non-sensitive)."""
    return ConfigValueResponse(
        code=0,
        message="ok",
        data={
            "scholar_provider": settings.scholar_provider,
            "enable_scholar_skill": settings.enable_scholar_skill,
            "openalex_api_key_set": bool(settings.openalex_api_key.strip()),
            "openalex_mailto": settings.openalex_mailto,
            "llm_provider": settings.llm_api_base_url,
            "llm_model": settings.llm_model_name,
        },
    )


@router.post("/reload", response_model=ConfigReloadResponse)
async def reload_config() -> ConfigReloadResponse:
    """
    Reload configuration from .env file.

    This endpoint reloads environment variables from the .env file
    without requiring a service restart.
    """
    try:
        settings.reload()
        return ConfigReloadResponse(
            code=0,
            message="Configuration reloaded successfully",
            data={
                "scholar_provider": settings.scholar_provider,
                "enable_scholar_skill": settings.enable_scholar_skill,
                "openalex_mailto": settings.openalex_mailto,
                "llm_model": settings.llm_model_name,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {exc}")
