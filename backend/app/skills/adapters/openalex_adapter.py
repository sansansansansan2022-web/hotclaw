"""Real OpenAlex adapter for paper discovery."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ConfigError, ExternalAPIError
from app.core.logger import get_logger

logger = get_logger(__name__)


class OpenAlexAdapter:
    """Thin OpenAlex client used by the scholar skill."""

    def __init__(self) -> None:
        self.base_url = settings.openalex_base_url.rstrip("/")
        self.timeout = settings.scholar_skill_timeout_seconds

    def validate_config(self) -> None:
        if not settings.enable_scholar_skill:
            raise ConfigError("Scholar skill is disabled. Set ENABLE_SCHOLAR_SKILL=1 to enable it.")
        if settings.scholar_provider.strip().lower() not in {"openalex", "openalex+crossref"}:
            raise ConfigError(
                "Scholar skill requires SCHOLAR_PROVIDER=openalex or SCHOLAR_PROVIDER=openalex+crossref."
            )
        if not settings.openalex_api_key.strip():
            raise ConfigError("Scholar skill requires OPENALEX_API_KEY for real OpenAlex access.")

    async def search_works(
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
            "search": self._build_search(topic, must_have, exclude_terms),
            "per-page": min(max(max_results * 3, 10), 30),
            "sort": "cited_by_count:desc",
            "api_key": settings.openalex_api_key.strip(),
        }
        if settings.openalex_mailto.strip():
            params["mailto"] = settings.openalex_mailto.strip()

        filters: list[str] = []
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")
        if paper_types:
            clean_types = [item.strip() for item in paper_types if item.strip()]
            if clean_types:
                filters.append("type:" + "|".join(clean_types))
        if filters:
            params["filter"] = ",".join(filters)

        url = f"{self.base_url}/works"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers={"User-Agent": "HotClaw/1.0"})
        except httpx.TimeoutException as exc:
            logger.error("openalex_request_timeout")
            raise ExternalAPIError("OpenAlex request timed out", details={"path": "/works"}) from exc
        except httpx.HTTPError as exc:
            logger.error("openalex_request_network_error", error=str(exc))
            raise ExternalAPIError("OpenAlex request failed", details={"path": "/works"}) from exc

        if response.status_code >= 400:
            raise ExternalAPIError(
                "OpenAlex request failed",
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


openalex_adapter = OpenAlexAdapter()
