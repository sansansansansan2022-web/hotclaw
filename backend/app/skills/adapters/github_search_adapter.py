"""Real GitHub REST adapters for repository discovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import settings
from app.core.exceptions import ConfigError, ExternalAPIError
from app.core.logger import get_logger

logger = get_logger(__name__)


class GitHubSearchAdapter:
    """Thin GitHub REST client used by the curator skill."""

    def __init__(self) -> None:
        self.base_url = settings.github_api_base_url.rstrip("/") + "/"
        self.timeout = settings.github_skill_timeout_seconds

    def validate_config(self) -> None:
        if not settings.enable_github_skill:
            raise ConfigError("GitHub skill is disabled. Set ENABLE_GITHUB_SKILL=1 to enable it.")
        if not settings.github_token.strip():
            raise ConfigError("GitHub skill requires GITHUB_TOKEN.")
        if settings.github_api_mode.strip().lower() != "rest":
            raise ConfigError("GitHub skill currently supports only GITHUB_API_MODE=rest.")

    async def search_repositories(
        self,
        *,
        topic: str,
        time_window: str | None,
        language_filters: list[str] | None,
        max_results: int,
        exclude_terms: list[str] | None,
        require_license: bool,
        prefer_active: bool,
        categories: list[str] | None,
    ) -> dict[str, Any]:
        self.validate_config()
        query = self._build_query(
            topic=topic,
            time_window=time_window,
            language_filters=language_filters,
            exclude_terms=exclude_terms,
            require_license=require_license,
            prefer_active=prefer_active,
            categories=categories,
        )
        per_page = min(max(max_results * 4, 10), 50)
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
            "page": 1,
        }
        response = await self._request("search/repositories", params=params)
        payload = response.json()
        return {
            "query": query,
            "items": payload.get("items", []),
        }

    async def fetch_readme(self, full_name: str) -> str | None:
        self.validate_config()
        try:
            response = await self._request(
                f"repos/{full_name}/readme",
                headers={"Accept": "application/vnd.github.raw+json"},
            )
        except ExternalAPIError as exc:
            details = exc.details or {}
            if details.get("status_code") == 404:
                return None
            raise
        return response.text or None

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        request_headers = {
            "Authorization": f"Bearer {settings.github_token.strip()}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "HotClaw/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if headers:
            request_headers.update(headers)

        url = urljoin(self.base_url, path)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=request_headers)
        except httpx.TimeoutException as exc:
            logger.error("github_request_timeout", path=path)
            raise ExternalAPIError("GitHub request timed out", details={"path": path}) from exc
        except httpx.HTTPError as exc:
            logger.error("github_request_network_error", path=path, error=str(exc))
            raise ExternalAPIError("GitHub request failed", details={"path": path}) from exc

        self._raise_for_status(response, path)
        return response

    def _raise_for_status(self, response: httpx.Response, path: str) -> None:
        if response.status_code < 400:
            return

        rate_limit_reset = response.headers.get("X-RateLimit-Reset")
        details = {
            "path": path,
            "status_code": response.status_code,
            "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
            "rate_limit_reset": rate_limit_reset,
        }
        if response.status_code in {401, 403} and response.headers.get("X-RateLimit-Remaining") == "0":
            raise ExternalAPIError("GitHub rate limit exceeded", details=details)
        if response.status_code in {401, 403}:
            raise ExternalAPIError("GitHub authentication failed", details=details)
        if response.status_code == 404:
            raise ExternalAPIError("GitHub resource not found", details=details)
        raise ExternalAPIError("GitHub request failed", details=details)

    def _build_query(
        self,
        *,
        topic: str,
        time_window: str | None,
        language_filters: list[str] | None,
        exclude_terms: list[str] | None,
        require_license: bool,
        prefer_active: bool,
        categories: list[str] | None,
    ) -> str:
        query_parts = [topic.strip(), "archived:false", "fork:false"]
        for language in language_filters or []:
            query_parts.append(f"language:{language}")
        if prefer_active:
            cutoff_days = self._parse_time_window_days(time_window) or 180
            cutoff = (datetime.now(timezone.utc) - timedelta(days=cutoff_days)).date().isoformat()
            query_parts.append(f"pushed:>={cutoff}")
        for term in exclude_terms or []:
            clean = term.strip()
            if clean:
                query_parts.append(f"-{clean}")
        if require_license:
            query_parts.append("license:mit")
        for category in categories or []:
            clean = category.strip()
            if clean:
                query_parts.append(clean)
        return " ".join(part for part in query_parts if part)

    def _parse_time_window_days(self, time_window: str | None) -> int | None:
        raw = (time_window or "").strip().lower()
        if not raw:
            return None
        if raw.endswith("d") and raw[:-1].isdigit():
            return int(raw[:-1])
        if raw.endswith("w") and raw[:-1].isdigit():
            return int(raw[:-1]) * 7
        if raw.endswith("m") and raw[:-1].isdigit():
            return int(raw[:-1]) * 30
        return None


github_search_adapter = GitHubSearchAdapter()
