"""Real Crossref adapter used for metadata enrichment."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalAPIError
from app.core.logger import get_logger

logger = get_logger(__name__)


def _get_proxy_url() -> str | None:
    """Get HTTP proxy URL from environment variables."""
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if http_proxy:
        return http_proxy
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return https_proxy


class CrossrefAdapter:
    """Crossref metadata enrichment client."""

    def __init__(self) -> None:
        self.base_url = settings.crossref_base_url.rstrip("/")
        self.timeout = settings.scholar_skill_timeout_seconds

    async def enrich_by_title(self, title: str) -> dict[str, Any] | None:
        if not title.strip():
            return None
        params = {
            "query.title": title.strip(),
            "rows": 3,
        }
        headers = {"User-Agent": self._user_agent()}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=_get_proxy_url(), trust_env=False) as client:
                response = await client.get(f"{self.base_url}/works", params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise ExternalAPIError("Crossref request timed out", details={"title": title}) from exc
        except httpx.HTTPError as exc:
            raise ExternalAPIError("Crossref request failed", details={"title": title}) from exc

        if response.status_code >= 400:
            raise ExternalAPIError(
                "Crossref request failed",
                details={"status_code": response.status_code, "title": title},
            )
        items = ((response.json() or {}).get("message") or {}).get("items") or []
        if not items:
            return None
        normalized_title = title.strip().lower()
        for item in items:
            candidate_title = " ".join(item.get("title") or []).strip().lower()
            if candidate_title == normalized_title:
                return item
        return items[0]

    def _user_agent(self) -> str:
        mailto = settings.crossref_mailto.strip()
        if mailto:
            return f"HotClaw/1.0 (mailto:{mailto})"
        return "HotClaw/1.0"


crossref_adapter = CrossrefAdapter()
