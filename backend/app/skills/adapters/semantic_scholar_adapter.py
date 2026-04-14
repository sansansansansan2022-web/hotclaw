"""Real Semantic Scholar adapter for paper discovery and enrichment."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ConfigError, ExternalAPIError
from app.core.logger import get_logger
from app.skills.adapters.scholar_provider_config import provider_includes

logger = get_logger(__name__)


def _get_proxy_url() -> str | None:
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if http_proxy:
        return http_proxy
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return https_proxy


class SemanticScholarAdapter:
    """Thin Semantic Scholar client used by the scholar skill."""

    def __init__(self) -> None:
        self.base_url = settings.semantic_scholar_base_url.rstrip("/")
        self.timeout = settings.scholar_skill_timeout_seconds

    def validate_config(self) -> None:
        if not settings.enable_scholar_skill:
            raise ConfigError("Scholar skill is disabled. Set ENABLE_SCHOLAR_SKILL=1 to enable it.")
        if not provider_includes(settings.scholar_provider, "semanticscholar"):
            raise ConfigError("Semantic Scholar adapter requires SCHOLAR_PROVIDER to include semanticscholar.")

    async def search_papers(
        self,
        *,
        topic: str,
        year_from: int | None,
        year_to: int | None,
        max_results: int,
        paper_types: list[str] | None,
        must_have: list[str] | None,
        exclude_terms: list[str] | None,
    ) -> dict[str, Any]:
        self.validate_config()
        params = {
            "query": self._build_search(topic, must_have, exclude_terms),
            "limit": min(max(max_results * 3, 10), 30),
            "fields": ",".join(
                [
                    "title",
                    "year",
                    "abstract",
                    "authors",
                    "citationCount",
                    "venue",
                    "publicationTypes",
                    "externalIds",
                    "url",
                    "publicationVenue",
                ]
            ),
        }
        if year_from:
            params["year"] = f"{year_from}-{year_to or year_from}"
        elif year_to:
            params["year"] = str(year_to)
        if paper_types:
            cleaned = [item.strip() for item in paper_types if item.strip()]
            if cleaned:
                params["publicationTypes"] = ",".join(cleaned)

        headers = {"User-Agent": "HotClaw/1.0"}
        api_key = settings.semantic_scholar_api_key.strip()
        if api_key:
            headers["x-api-key"] = api_key

        url = f"{self.base_url}/graph/v1/paper/search"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, proxy=_get_proxy_url(), trust_env=False) as client:
                response = await client.get(url, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            logger.error("semantic_scholar_request_timeout")
            raise ExternalAPIError("Semantic Scholar request timed out", details={"path": "/graph/v1/paper/search"}) from exc
        except httpx.HTTPError as exc:
            logger.error("semantic_scholar_request_network_error", error=str(exc))
            raise ExternalAPIError("Semantic Scholar request failed", details={"path": "/graph/v1/paper/search"}) from exc

        if response.status_code >= 400:
            raise ExternalAPIError(
                f"Semantic Scholar request failed with HTTP {response.status_code}",
                details={"status_code": response.status_code, "body": response.text[:300]},
            )
        return response.json()

    def _build_search(
        self,
        topic: str,
        must_have: list[str] | None,
        exclude_terms: list[str] | None,
    ) -> str:
        parts = [topic.strip()]
        parts.extend(item.strip() for item in must_have or [] if item.strip())
        parts.extend(f"-{item.strip()}" for item in exclude_terms or [] if item.strip())
        return " ".join(part for part in parts if part)


semantic_scholar_adapter = SemanticScholarAdapter()
