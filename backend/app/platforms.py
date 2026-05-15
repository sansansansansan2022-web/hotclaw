"""Content platform helpers shared by account-aware services and agents."""

from __future__ import annotations

from typing import Any


SUPPORTED_CONTENT_PLATFORMS = {"wechat", "xiaohongshu"}
DEFAULT_CONTENT_PLATFORM = "wechat"


def normalize_content_platform(value: Any) -> str:
    clean = str(value or "").strip().lower()
    if clean in {"xhs", "red", "rednote", "xiaohongshu", "小红书"}:
        return "xiaohongshu"
    if clean in {"wechat", "weixin", "mp", "official_account", "公众号", "微信"}:
        return "wechat"
    return DEFAULT_CONTENT_PLATFORM


def resolve_content_platform(*contexts: dict[str, Any] | None) -> str:
    for context in contexts:
        if not isinstance(context, dict):
            continue
        for key in ("content_platform", "platform", "target_platform"):
            value = context.get(key)
            if value:
                return normalize_content_platform(value)
    return DEFAULT_CONTENT_PLATFORM


def platform_label(platform: str) -> str:
    return "小红书" if normalize_content_platform(platform) == "xiaohongshu" else "微信公众号"


def collect_platform_prompt_hints(context: dict[str, Any] | None, key: str) -> list[str]:
    if not isinstance(context, dict):
        return []
    capabilities = context.get("platform_capabilities")
    if not isinstance(capabilities, dict):
        return []
    prompt_hints = capabilities.get("prompt_hints")
    if not isinstance(prompt_hints, dict):
        return []
    raw_items = prompt_hints.get(key) or []
    if isinstance(raw_items, str):
        raw_items = [raw_items]
    return [str(item).strip() for item in raw_items if str(item).strip()]
