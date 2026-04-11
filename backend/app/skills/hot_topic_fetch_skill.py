"""Hot topic fetch skill for lightweight source scouting."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from app.core.logger import get_logger
from app.skills.base import BaseSkill

logger = get_logger(__name__)

SEARCH_ENGINES = [
    {
        "name": "Weixin Search",
        "source": "weixin",
        "url_template": "https://wx.sogou.com/weixin?type=2&query={query}",
    },
    {
        "name": "Sogou",
        "source": "sogou",
        "url_template": "https://sogou.com/web?query={query}",
    },
    {
        "name": "360 Search",
        "source": "360",
        "url_template": "https://www.so.com/s?q={query}",
    },
]


class HotTopicFetchSkill(BaseSkill):
    """Fetch and normalize lightweight hot-topic candidates from public search pages."""

    skill_id = "hot_topic_fetch_skill"
    name = "Hot Topic Fetch Skill"
    description = "Fetches and normalizes hot topic candidates from multiple search engines."

    input_schema = {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional prebuilt search queries."
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Keyword list used when prebuilt queries are not provided."
            },
            "engines": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["weixin", "sogou", "360"],
            },
            "max_results_per_engine": {
                "type": "integer",
                "default": 8,
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "source": {"type": "string"},
                        "source_type": {"type": "string"},
                        "url": {"type": "string"},
                        "snippet": {"type": "string"},
                    },
                },
            },
            "total_count": {"type": "integer"},
            "engines_used": {"type": "array", "items": {"type": "string"}},
        },
    }

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.timeout = config.get("timeout_seconds", 10) if config else 10
        self.max_results = config.get("max_results_per_engine", 8) if config else 8

    async def execute(self, input_data: dict) -> dict:
        queries = [
            str(item).strip()
            for item in (input_data.get("queries") or [])
            if str(item).strip()
        ]
        keywords = [
            str(item).strip()
            for item in (input_data.get("keywords") or [])
            if str(item).strip()
        ]
        if not queries and not keywords:
            return self._failure_output("keywords_required", "keywords parameter cannot be empty")

        search_queries = queries or [self._build_search_query(keywords)]
        engines = input_data.get("engines", ["weixin", "sogou", "360"])
        max_results = int(input_data.get("max_results_per_engine", self.max_results) or self.max_results)

        try:
            results, engines_used = await self._fetch_all_queries(search_queries, engines, max_results)
            return self._success_output(results, engines_used)
        except Exception as exc:
            logger.error("hot_topic_fetch_skill_error", error=str(exc))
            return self._failure_output("fetch_error", str(exc))

    def _build_search_query(self, keywords: list[str]) -> str:
        if len(keywords) >= 2:
            return "+".join(keywords[:2]) + "+热点"
        if keywords:
            return f"{keywords[0]}+热点"
        return "热点"

    async def _fetch_all_queries(
        self,
        queries: list[str],
        engine_names: list[str],
        max_results: int,
    ) -> tuple[list[dict], list[str]]:
        all_results: list[dict] = []
        engines_used: list[str] = []

        for query in queries:
            results, used = await self._fetch_all_engines(query, engine_names, max_results)
            all_results.extend(results)
            engines_used.extend(used)

        unique_engines: list[str] = []
        for engine in engines_used:
            if engine not in unique_engines:
                unique_engines.append(engine)
        return self._deduplicate(all_results, max_results), unique_engines

    async def _fetch_all_engines(
        self,
        query: str,
        engine_names: list[str],
        max_results: int,
    ) -> tuple[list[dict], list[str]]:
        results: list[dict] = []
        engines_used: list[str] = []
        engines_to_fetch = [engine for engine in SEARCH_ENGINES if engine["source"] in engine_names]

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=5.0),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        ) as client:
            tasks = []
            for engine in engines_to_fetch:
                url = engine["url_template"].format(query=query)
                tasks.append(self._fetch_engine(client, url, engine))

            engine_results = await asyncio.gather(*tasks, return_exceptions=True)

        for engine, result in zip(engines_to_fetch, engine_results):
            if isinstance(result, list) and result:
                results.extend(result)
                engines_used.append(engine["source"])
            elif isinstance(result, Exception):
                logger.warning("engine_fetch_failed", engine=engine["source"], error=str(result))

        return self._deduplicate(results, max_results), engines_used

    async def _fetch_engine(
        self,
        client: httpx.AsyncClient,
        url: str,
        engine: dict[str, str],
    ) -> list[dict[str, Any]]:
        try:
            response = await client.get(url)
            response.raise_for_status()

            if engine["source"] == "weixin":
                return self._parse_weixin(response.text, engine["name"])
            if engine["source"] == "sogou":
                return self._parse_sogou(response.text, engine["name"])
            if engine["source"] == "360":
                return self._parse_360(response.text, engine["name"])
            return []
        except Exception as exc:
            logger.warning("engine_fetch_error", engine=engine["name"], error=str(exc))
            return []

    def _parse_weixin(self, html: str, source: str) -> list[dict[str, Any]]:
        return self._parse_titles(
            html,
            source=source,
            source_type="weixin",
            patterns=[
                r'<h3[^>]*class="tit"[^>]*>.*?<a[^>]*>(.*?)</a>',
                r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
                r'class="s-p"[^>]*>.*?<a[^>]*>(.*?)</a>',
            ],
        )

    def _parse_sogou(self, html: str, source: str) -> list[dict[str, Any]]:
        return self._parse_titles(
            html,
            source=source,
            source_type="sogou",
            patterns=[
                r'class="vrTitle"[^>]*>.*?<a[^>]*>(.*?)</a>',
                r'class="pt"[^>]*>.*?<a[^>]*>(.*?)</a>',
                r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
            ],
        )

    def _parse_360(self, html: str, source: str) -> list[dict[str, Any]]:
        return self._parse_titles(
            html,
            source=source,
            source_type="360",
            patterns=[
                r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
                r'class="res-title"[^>]*>.*?<a[^>]*>(.*?)</a>',
            ],
        )

    def _parse_titles(
        self,
        html: str,
        *,
        source: str,
        source_type: str,
        patterns: list[str],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                title = re.sub(r"<[^>]+>", "", match).strip()
                if not title or len(title) <= 5:
                    continue
                results.append(
                    {
                        "title": title,
                        "source": source,
                        "source_type": source_type,
                        "url": "",
                        "snippet": title[:80],
                    }
                )
        return results[:8]

    def _deduplicate(self, results: list[dict], max_total: int) -> list[dict]:
        seen_titles: set[str] = set()
        deduped: list[dict] = []
        for result in results:
            title = str(result.get("title") or "").strip()
            if not title:
                continue
            normalized = re.sub(r"[\s\W]", "", title.lower())
            if normalized in seen_titles:
                continue
            if len(title) < 5 or len(title) > 100:
                continue
            seen_titles.add(normalized)
            deduped.append(result)
            if len(deduped) >= max_total:
                break
        return deduped

    def _success_output(self, results: list[dict], engines_used: list[str]) -> dict:
        return {
            "status": "success",
            "skill_id": self.skill_id,
            "data": {
                "results": results,
                "total_count": len(results),
                "engines_used": engines_used,
            },
            "error": None,
        }

    def _failure_output(self, code: str, message: str) -> dict:
        return {
            "status": "failed",
            "skill_id": self.skill_id,
            "data": None,
            "error": {"code": code, "message": message},
        }
