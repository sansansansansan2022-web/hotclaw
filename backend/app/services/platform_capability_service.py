"""Plugin-like platform capability registry and runtime resolver."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import PlatformCapabilityModel
from app.platforms import normalize_content_platform


DEFAULT_PLATFORM_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "wechat.recommendation.public_search",
        "content_platform": "wechat",
        "capability_type": "recommendation",
        "name": "微信公众号选题推荐",
        "description": "用公共搜索、参考源和账号画像生成公众号长文选题推荐。",
        "config_json": {
            "source_types": ["public_search", "news_article", "reference_source"],
            "output_shape": "long_form_topic_package",
            "ranking_weights": {"account_fit": 0.3, "freshness": 0.2, "authority": 0.2, "relevance": 0.3},
        },
        "prompt_overrides_json": {
            "recommendation": "解释为公众号长文选题：观点角度、为什么现在写、证据基础和目标读者。",
        },
    },
    {
        "capability_id": "wechat.layout.inline_html",
        "content_platform": "wechat",
        "capability_type": "layout",
        "name": "公众号内联 HTML 排版",
        "description": "生成移动端长读友好的公众号内联 HTML 和封面图建议。",
        "config_json": {
            "templates": ["insight_column", "briefing_digest", "warm_story", "operator_playbook"],
            "content_format": "wechat_inline_html",
        },
        "prompt_overrides_json": {
            "post_process": "保持公众号兼容排版、分节层级、导读卡片和审稿清单。",
        },
    },
    {
        "capability_id": "xiaohongshu.analysis.image_text_account",
        "content_platform": "xiaohongshu",
        "capability_type": "analysis",
        "name": "小红书图文账号分析",
        "description": "分析小红书图文账号的封面钩子、卡片节奏、前三行、标签和互动方式。",
        "config_json": {
            "style_dimensions": ["cover_hook", "first_card_promise", "card_sequence", "first_three_lines", "tags", "comment_hook"],
            "evidence_unit": "image_text_note",
        },
        "prompt_overrides_json": {
            "account_analysis": "重点分析封面、首图、滑动卡片、正文前三行、标签/搜索词和评论互动。",
        },
    },
    {
        "capability_id": "xiaohongshu.recommendation.note_scout",
        "content_platform": "xiaohongshu",
        "capability_type": "recommendation",
        "name": "小红书笔记推荐",
        "description": "把推荐内容转成笔记选题、封面承诺、滑动卡片和互动钩子。",
        "config_json": {
            "source_types": ["xiaohongshu_note_scout", "reference_source", "public_search"],
            "output_shape": "image_text_note_package",
            "ranking_weights": {"platform_fit": 0.22, "save_value": 0.2, "account_fit": 0.28, "freshness": 0.12, "relevance": 0.18},
        },
        "prompt_overrides_json": {
            "recommendation": "解释为小红书图文笔记：封面标题、卡片顺序、收藏价值、标签方向和评论触发点。",
        },
    },
    {
        "capability_id": "xiaohongshu.layout.cover_cards",
        "content_platform": "xiaohongshu",
        "capability_type": "layout",
        "name": "小红书封面卡片排版",
        "description": "生成小红书方图封面、3-6 张卡片结构、短正文和互动结尾。",
        "config_json": {
            "templates": ["xhs_cover_cards", "xhs_clean_note"],
            "content_format": "xiaohongshu_image_text_note",
            "recommended_card_count": [3, 6],
        },
        "prompt_overrides_json": {
            "post_process": "产物以封面承诺、滑动卡片、短笔记正文和评论钩子组织。",
        },
    },
)


class PlatformCapabilityService:
    """Resolve builtin and stored platform capabilities into effective runtime config."""

    def __init__(self) -> None:
        self._defaults = {item["capability_id"]: dict(item) for item in DEFAULT_PLATFORM_CAPABILITIES}

    async def list_capabilities(
        self,
        db: AsyncSession,
        *,
        content_platform: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        stored_rows = await self._list_stored(db)
        stored_by_id = {row.capability_id: row for row in stored_rows}
        ids = set(self._defaults) | set(stored_by_id)
        rows = [self._serialize_effective(capability_id, stored_by_id.get(capability_id)) for capability_id in sorted(ids)]
        platform = normalize_content_platform(content_platform) if content_platform else None
        if platform:
            rows = [row for row in rows if row["content_platform"] == platform]
        if not include_deleted:
            rows = [row for row in rows if row["status"] != "deleted"]
        return rows

    async def get_effective_capabilities(self, content_platform: str, db: AsyncSession) -> dict[str, Any]:
        platform = normalize_content_platform(content_platform)
        capabilities = [
            row
            for row in await self.list_capabilities(db, content_platform=platform)
            if row["status"] == "active" and row["is_enabled"]
        ]
        by_type: dict[str, list[dict[str, Any]]] = {}
        prompt_hints: dict[str, list[str]] = {}
        for row in capabilities:
            by_type.setdefault(row["capability_type"], []).append(row)
            for key, value in (row.get("prompt_overrides_json") or {}).items():
                if isinstance(value, str) and value.strip():
                    prompt_hints.setdefault(str(key), []).append(value.strip())
        return {
            "content_platform": platform,
            "capabilities": capabilities,
            "by_type": by_type,
            "prompt_hints": prompt_hints,
        }

    async def create_capability(self, payload: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
        platform = normalize_content_platform(payload.get("content_platform"))
        capability_type = self._clean_slug(payload.get("capability_type") or "custom", max_length=64) or "custom"
        capability_id = self._normalize_capability_id(
            payload.get("capability_id")
            or self._build_capability_id(
                platform=platform,
                capability_type=capability_type,
                name=payload.get("name"),
            )
        )
        existing = await db.get(PlatformCapabilityModel, capability_id)
        if existing is not None or capability_id in self._defaults:
            raise ValueError(f"capability already exists: {capability_id}")
        row = PlatformCapabilityModel(
            capability_id=capability_id,
            content_platform=platform,
            capability_type=capability_type,
            name=str(payload.get("name") or capability_id).strip(),
            description=payload.get("description"),
            is_builtin=False,
            is_enabled=bool(payload.get("is_enabled", True)),
            status="active",
            config_json=self._as_dict(payload.get("config_json")),
            prompt_overrides_json=self._as_dict(payload.get("prompt_overrides_json")),
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return self._serialize_effective(capability_id, row)

    async def update_capability(self, capability_id: str, payload: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
        normalized_id = self._normalize_capability_id(capability_id)
        row = await db.get(PlatformCapabilityModel, normalized_id)
        if row is None:
            default = self._defaults.get(normalized_id)
            if default is None:
                raise KeyError(normalized_id)
            row = PlatformCapabilityModel(
                capability_id=normalized_id,
                content_platform=default["content_platform"],
                capability_type=default["capability_type"],
                name=default["name"],
                description=default.get("description"),
                is_builtin=True,
                is_enabled=True,
                status="active",
                config_json=dict(default.get("config_json") or {}),
                prompt_overrides_json=dict(default.get("prompt_overrides_json") or {}),
            )
            db.add(row)

        if payload.get("content_platform") is not None:
            row.content_platform = normalize_content_platform(payload.get("content_platform"))
        if payload.get("capability_type") is not None:
            row.capability_type = self._clean_slug(payload.get("capability_type") or row.capability_type, max_length=64)
        if payload.get("name") is not None:
            row.name = str(payload.get("name") or row.name).strip()
        if "description" in payload:
            row.description = payload.get("description")
        if payload.get("is_enabled") is not None:
            row.is_enabled = bool(payload.get("is_enabled"))
        if payload.get("status") is not None:
            row.status = self._normalize_status(payload.get("status"))
        if payload.get("config_json") is not None:
            row.config_json = self._as_dict(payload.get("config_json"))
        if payload.get("prompt_overrides_json") is not None:
            row.prompt_overrides_json = self._as_dict(payload.get("prompt_overrides_json"))

        await db.flush()
        await db.refresh(row)
        return self._serialize_effective(normalized_id, row)

    async def delete_capability(self, capability_id: str, db: AsyncSession) -> dict[str, Any]:
        normalized_id = self._normalize_capability_id(capability_id)
        row = await db.get(PlatformCapabilityModel, normalized_id)
        if row is None:
            default = self._defaults.get(normalized_id)
            if default is None:
                raise KeyError(normalized_id)
            row = PlatformCapabilityModel(
                capability_id=normalized_id,
                content_platform=default["content_platform"],
                capability_type=default["capability_type"],
                name=default["name"],
                description=default.get("description"),
                is_builtin=True,
                is_enabled=False,
                status="deleted",
                config_json=dict(default.get("config_json") or {}),
                prompt_overrides_json=dict(default.get("prompt_overrides_json") or {}),
            )
            db.add(row)
        else:
            row.status = "deleted"
            row.is_enabled = False
        await db.flush()
        await db.refresh(row)
        return self._serialize_effective(normalized_id, row)

    async def restore_capability(self, capability_id: str, db: AsyncSession) -> dict[str, Any]:
        normalized_id = self._normalize_capability_id(capability_id)
        row = await db.get(PlatformCapabilityModel, normalized_id)
        if row is None and normalized_id not in self._defaults:
            raise KeyError(normalized_id)
        if row is None:
            return self._serialize_effective(normalized_id, None)
        row.status = "active"
        row.is_enabled = True
        await db.flush()
        await db.refresh(row)
        return self._serialize_effective(normalized_id, row)

    async def _list_stored(self, db: AsyncSession) -> list[PlatformCapabilityModel]:
        result = await db.execute(select(PlatformCapabilityModel).order_by(PlatformCapabilityModel.content_platform, PlatformCapabilityModel.capability_type, PlatformCapabilityModel.capability_id))
        return list(result.scalars().all())

    def _serialize_effective(self, capability_id: str, row: PlatformCapabilityModel | None) -> dict[str, Any]:
        default = self._defaults.get(capability_id, {})
        is_builtin = bool(default) or bool(row.is_builtin if row else False)
        status = row.status if row else "active"
        config = dict(default.get("config_json") or {})
        config.update(self._as_dict(row.config_json if row else None))
        prompt_overrides = dict(default.get("prompt_overrides_json") or {})
        prompt_overrides.update(self._as_dict(row.prompt_overrides_json if row else None))
        return {
            "capability_id": capability_id,
            "content_platform": normalize_content_platform((row.content_platform if row else None) or default.get("content_platform")),
            "capability_type": str((row.capability_type if row else None) or default.get("capability_type") or "custom"),
            "name": str((row.name if row else None) or default.get("name") or capability_id),
            "description": (row.description if row else None) if row and row.description is not None else default.get("description"),
            "is_builtin": is_builtin,
            "is_enabled": bool(row.is_enabled) if row else True,
            "status": status,
            "config_json": config,
            "prompt_overrides_json": prompt_overrides,
            "source": "custom" if not is_builtin else ("overridden" if row else "builtin"),
            "created_at": self._serialize_datetime(row.created_at) if row else None,
            "updated_at": self._serialize_datetime(row.updated_at) if row else None,
        }

    def _normalize_capability_id(self, value: Any) -> str:
        clean = self._clean_slug(value, max_length=128)
        if not clean:
            raise ValueError("capability_id is required")
        return clean

    def _build_capability_id(self, *, platform: str, capability_type: str, name: Any) -> str:
        name_slug = self._clean_slug(name, max_length=48)
        suffix = name_slug or uuid4().hex[:8]
        return f"{platform}.{capability_type}.{suffix}"

    def _clean_slug(self, value: Any, *, max_length: int) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[^a-z0-9_.-]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("._-")
        return text[:max_length]

    def _normalize_status(self, value: Any) -> str:
        clean = str(value or "").strip().lower()
        return clean if clean in {"active", "deleted"} else "active"

    def _as_dict(self, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    def _serialize_datetime(self, value: datetime | None) -> str | None:
        return value.isoformat() if isinstance(value, datetime) else None


platform_capability_service = PlatformCapabilityService()
