"""Database-backed cache for external skill responses."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.models.tables import SkillCacheModel

logger = get_logger(__name__)


class SkillCacheService:
    """Read and write stable skill responses."""

    def build_request_fingerprint(self, skill_name: str, input_data: dict[str, Any]) -> str:
        serialized = json.dumps(input_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(f"{skill_name}:{serialized}".encode("utf-8")).hexdigest()

    def build_cache_key(self, skill_name: str, request_fingerprint: str) -> str:
        return sha256(f"{skill_name}:{request_fingerprint}".encode("utf-8")).hexdigest()

    async def get(self, db: AsyncSession, *, skill_name: str, request_fingerprint: str) -> dict[str, Any] | None:
        cache_key = self.build_cache_key(skill_name, request_fingerprint)
        result = await db.execute(select(SkillCacheModel).where(SkillCacheModel.cache_key == cache_key))
        cache = result.scalar_one_or_none()
        if cache is None:
            return None
        expires_at = cache.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            logger.info("skill_cache_expired", skill_name=skill_name, cache_key=cache_key)
            return None
        logger.info("skill_cache_hit", skill_name=skill_name, cache_key=cache_key)
        return cache.response_json

    async def set(
        self,
        db: AsyncSession,
        *,
        skill_name: str,
        request_fingerprint: str,
        response_json: dict[str, Any],
    ) -> None:
        cache_key = self.build_cache_key(skill_name, request_fingerprint)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.skill_cache_ttl_seconds)
        result = await db.execute(select(SkillCacheModel).where(SkillCacheModel.cache_key == cache_key))
        cache = result.scalar_one_or_none()
        if cache is None:
            cache = SkillCacheModel(
                cache_key=cache_key,
                skill_name=skill_name,
                request_fingerprint=request_fingerprint,
                response_json=response_json,
                expires_at=expires_at,
            )
        else:
            cache.response_json = response_json
            cache.expires_at = expires_at
        db.add(cache)
        await db.flush()
        logger.info("skill_cache_written", skill_name=skill_name, cache_key=cache_key)


skill_cache_service = SkillCacheService()
