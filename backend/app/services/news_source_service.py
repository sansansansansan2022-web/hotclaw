"""Real news source collection for recommendation refresh."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import httpx

from app.core.config import settings
from app.core.logger import get_logger
from app.services.wechat_article_search_service import wechat_article_search_service

logger = get_logger(__name__)

# 国内可达的 RSS 源列表
# 注意：Google News RSS (news.google.com) 国内被屏蔽，已移除
# 注意：GitHub Blog (github.blog) 返回 404，已移除
# 注意：HuggingFace Blog 超时，已移除
# 注意：知乎 RSS (zhihu.com/rss) 需要登录，已移除
# 注意：36Kr (36kr.com/feed) 被 Cloudflare 拦截，已移除
DEFAULT_NEWS_FEEDS: list[dict[str, Any]] = [
    # === 国内可达源 ===
    {
        "key": "ithome_rss",
        "label": "IT之家",
        "url": "https://www.ithome.com.tw/rss",
        "authority": 0.68,
        "tags": ["科技", "数码", "硬件", "软件", "ai"],
    },
    # === 海外可达源 ===
    {
        "key": "openai_news",
        "label": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
        "authority": 0.90,
        "tags": ["ai", "llm", "model", "product", "developer", "tool"],
    },
    {
        "key": "techcrunch_ai",
        "label": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "authority": 0.76,
        "tags": ["ai", "startup", "product", "technology", "industry"],
    },
    {
        "key": "venturebeat_ai",
        "label": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "authority": 0.74,
        "tags": ["ai", "enterprise", "agent", "llm", "developer", "industry"],
    },
    {
        "key": "theverge_ai",
        "label": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "authority": 0.74,
        "tags": ["ai", "product", "technology", "industry", "agent"],
    },
    {
        "key": "ai_news",
        "label": "AI News",
        "url": "https://www.artificialintelligence-news.com/feed/",
        "authority": 0.70,
        "tags": ["ai", "enterprise", "agent", "llm", "model", "industry"],
    },
]


class NewsSourceService:
    """Fetch real-time news/article candidates from real RSS and Atom sources."""

    def __init__(self) -> None:
        self.timeout_seconds = max(int(getattr(settings, "news_feed_timeout_seconds", 15) or 15), 5)
        self.max_query_results = max(int(getattr(settings, "news_feed_max_results_per_query", 6) or 6), 3)

    def _get_proxy_url(self) -> str | None:
        """Get HTTP proxy URL from environment variables."""
        import os
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if http_proxy:
            return http_proxy
        # 也检查 HTTPS_PROXY 作为回退
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        return https_proxy

    async def collect_candidates(
        self,
        *,
        snapshot,
        query_plan: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not getattr(settings, "enable_news_feed_source", True):
            return [], [
                {
                    "source_key": "news_feed_runtime",
                    "label": "Real News Feeds",
                    "source_type": "news_article",
                    "status": "disabled",
                    "query": None,
                    "candidate_count": 0,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": "news_feed_disabled",
                    "error_message": "ENABLE_NEWS_FEED_SOURCE is disabled.",
                    "detail": "Real RSS/Atom news feeds are disabled for recommendation refresh.",
                }
            ]

        diagnostics: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        account_keywords = self._build_account_keywords(snapshot=snapshot, query_plan=query_plan)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=min(4.0, float(self.timeout_seconds))),
            follow_redirects=True,
            headers={
                "User-Agent": "HotClawNewsCollector/1.0 (+https://github.com/sansansansansan2022-web/hotclaw)"
            },
            proxy=self._get_proxy_url(),
            trust_env=False,
        ) as client:
            query_candidates, query_diagnostics = await self._collect_google_news_queries(
                client=client,
                query_plan=query_plan,
                account_keywords=account_keywords,
            )
            candidates.extend(query_candidates)
            diagnostics.extend(query_diagnostics)

            wechat_candidates, wechat_diagnostics = await self._collect_wechat_article_search(
                query_plan=query_plan,
                account_keywords=account_keywords,
            )
            candidates.extend(wechat_candidates)
            diagnostics.extend(wechat_diagnostics)

            curated_candidates, curated_diagnostics = await self._collect_curated_feeds(
                client=client,
                account_keywords=account_keywords,
                query_plan=query_plan,
            )
            candidates.extend(curated_candidates)
            diagnostics.extend(curated_diagnostics)

        return self._deduplicate_candidates(candidates), diagnostics

    async def _collect_google_news_queries(
        self,
        *,
        client: httpx.AsyncClient,
        query_plan: dict[str, Any],
        account_keywords: list[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        candidates: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []

        raw_queries = [
            *[str(item).strip() for item in (query_plan.get("primary_queries") or []) if str(item).strip()],
            *[str(item).strip() for item in (query_plan.get("secondary_queries") or []) if str(item).strip()],
        ]
        if not raw_queries:
            raw_queries = [str(item).strip() for item in (query_plan.get("search_terms") or []) if str(item).strip()]
        live_queries = [
            "AI agents",
            "LLM agents",
            "AI coding tools",
            "artificial intelligence startups",
        ]
        queries = self._dedupe_strings([*live_queries, *raw_queries])[:4]
        if not queries:
            diagnostics.append(
                {
                    "source_key": "google_news_rss",
                    "label": "Google News RSS",
                    "source_type": "news_article",
                    "status": "not_applicable",
                    "query": None,
                    "candidate_count": 0,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": "missing_query_plan",
                    "error_message": None,
                    "detail": "No query plan terms were available for Google News RSS search.",
                }
            )
            return candidates, diagnostics

        async def _fetch_query(query: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            feed_url = (
                "https://news.google.com/rss/search?"
                f"q={quote_plus(query + ' when:1d')}&hl=en-US&gl=US&ceid=US:en"
            )
            try:
                response = await client.get(feed_url)
                response.raise_for_status()
                entries = self._parse_feed_entries(response.text, default_source_name="Google News")
                query_candidates = [
                    self._build_news_candidate(
                        entry,
                        source_key="google_news_rss",
                        source_label="Google News RSS",
                        base_authority=0.62,
                        query=query,
                        account_keywords=account_keywords,
                        topic_tags=self._derive_topic_tags(query),
                    )
                    for entry in entries[: self.max_query_results]
                    if entry.get("title")
                ]
                query_candidates = [item for item in query_candidates if item]
                return query_candidates, {
                    "source_key": "google_news_rss",
                    "label": "Google News RSS",
                    "source_type": "news_article",
                    "status": "success" if query_candidates else "empty",
                    "query": query,
                    "candidate_count": len(query_candidates),
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": None,
                    "error_message": None,
                    "detail": None if query_candidates else "Feed request succeeded but did not return usable entries.",
                }
            except httpx.HTTPStatusError as exc:
                error_detail = f"HTTP {exc.response.status_code}"
                logger.warning(
                    "google_news_feed_failed",
                    query=query,
                    status_code=exc.response.status_code,
                    error=error_detail,
                )
                return [], {
                    "source_key": "google_news_rss",
                    "label": "Google News RSS",
                    "source_type": "news_article",
                    "status": "failed",
                    "query": query,
                    "candidate_count": 0,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": "google_news_http_error",
                    "error_message": error_detail,
                    "detail": f"Google News returned HTTP {exc.response.status_code}",
                }
            except Exception as exc:
                error_msg = str(exc) or type(exc).__name__
                logger.warning("google_news_feed_failed", query=query, error=error_msg)
                return [], {
                    "source_key": "google_news_rss",
                    "label": "Google News RSS",
                    "source_type": "news_article",
                    "status": "failed",
                    "query": query,
                    "candidate_count": 0,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": "google_news_fetch_failed",
                    "error_message": error_msg,
                    "detail": f"{type(exc).__name__}: {error_msg}",
                }
        results = await asyncio.gather(*[_fetch_query(query) for query in queries], return_exceptions=False)
        for query_candidates, query_diagnostic in results:
            candidates.extend(query_candidates)
            diagnostics.append(query_diagnostic)
        return candidates, diagnostics

    async def _collect_wechat_article_search(
        self,
        *,
        query_plan: dict[str, Any],
        account_keywords: list[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        raw_queries = [
            *[str(item).strip() for item in (query_plan.get("primary_queries") or []) if str(item).strip()],
            *[str(item).strip() for item in (query_plan.get("search_terms") or []) if str(item).strip()],
        ]
        queries = self._dedupe_strings(raw_queries)[:2]
        if not queries:
            return [], [
                {
                    "source_key": "wechat_article_search",
                    "label": "WeChat Article Search",
                    "source_type": "news_article",
                    "status": "not_applicable",
                    "query": None,
                    "candidate_count": 0,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": "missing_query_plan",
                    "error_message": None,
                    "detail": "No usable query terms were available for WeChat article search.",
                }
            ]

        candidates: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        for query in queries:
            try:
                articles = await wechat_article_search_service.search_articles(
                    query=query,
                    max_results=self.max_query_results,
                    resolve_real_urls=False,
                )
                mapped = [
                    self._build_wechat_candidate(
                        article,
                        query=query,
                        account_keywords=account_keywords,
                    )
                    for article in articles
                ]
                usable = [item for item in mapped if item]
                candidates.extend(usable)
                diagnostics.append(
                    {
                        "source_key": "wechat_article_search",
                        "label": "WeChat Article Search",
                        "source_type": "news_article",
                        "status": "success" if usable else "empty",
                        "query": query,
                        "candidate_count": len(usable),
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": None,
                        "error_message": None,
                        "detail": None if usable else "Search request succeeded but produced no usable article rows.",
                    }
                )
            except Exception as exc:
                error_msg = str(exc) or type(exc).__name__
                logger.warning("wechat_article_search_failed", query=query, error=error_msg)
                diagnostics.append(
                    {
                        "source_key": "wechat_article_search",
                        "label": "WeChat Article Search",
                        "source_type": "news_article",
                        "status": "failed",
                        "query": query,
                        "candidate_count": 0,
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": "wechat_article_search_failed",
                        "error_message": error_msg,
                        "detail": f"{type(exc).__name__}: {error_msg}",
                    }
                )
        return candidates, diagnostics

    async def _collect_curated_feeds(
        self,
        *,
        client: httpx.AsyncClient,
        account_keywords: list[str],
        query_plan: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        candidates: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        lane_label = str(((query_plan.get("lane") or {}).get("label")) or "").strip()

        selected_feeds = self._select_curated_feeds(account_keywords)
        for feed in selected_feeds:
            try:
                response = await client.get(feed["url"])
                response.raise_for_status()
                entries = self._parse_feed_entries(response.text, default_source_name=feed["label"])
                feed_candidates = [
                    self._build_news_candidate(
                        entry,
                        source_key=feed["key"],
                        source_label=feed["label"],
                        base_authority=float(feed["authority"]),
                        query=lane_label or None,
                        account_keywords=account_keywords,
                        topic_tags=self._dedupe_strings([lane_label, *feed.get("tags", [])])[:5],
                    )
                    for entry in entries[: self.max_query_results]
                    if entry.get("title")
                ]
                feed_candidates = [item for item in feed_candidates if item]
                candidates.extend(feed_candidates)
                diagnostics.append(
                    {
                        "source_key": feed["key"],
                        "label": feed["label"],
                        "source_type": "news_article",
                        "status": "success" if feed_candidates else "empty",
                        "query": None,
                        "candidate_count": len(feed_candidates),
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": None,
                        "error_message": None,
                        "detail": None if feed_candidates else "Feed request succeeded but did not return usable entries.",
                    }
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "curated_news_feed_failed",
                    source_key=feed["key"],
                    status_code=exc.response.status_code,
                    error=f"HTTP {exc.response.status_code}: {exc.response.text[:200] if exc.response.text else 'empty'}",
                )
                diagnostics.append(
                    {
                        "source_key": feed["key"],
                        "label": feed["label"],
                        "source_type": "news_article",
                        "status": "failed",
                        "query": None,
                        "candidate_count": 0,
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": "curated_feed_http_error",
                        "error_message": f"HTTP {exc.response.status_code}",
                        "detail": f"HTTP {exc.response.status_code}: {exc.response.text[:200] if exc.response.text else 'empty'}",
                    }
                )
            except Exception as exc:
                error_msg = str(exc) or type(exc).__name__
                logger.warning(
                    "curated_news_feed_failed",
                    source_key=feed["key"],
                    error=error_msg,
                )
                diagnostics.append(
                    {
                        "source_key": feed["key"],
                        "label": feed["label"],
                        "source_type": "news_article",
                        "status": "failed",
                        "query": None,
                        "candidate_count": 0,
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": "curated_feed_fetch_failed",
                        "error_message": error_msg,
                        "detail": f"{type(exc).__name__}: {error_msg}",
                    }
                )
        return candidates, diagnostics

    def _select_curated_feeds(self, account_keywords: list[str]) -> list[dict[str, Any]]:
        scored: list[tuple[int, dict[str, Any]]] = []
        keyword_set = {keyword.lower() for keyword in account_keywords}
        for feed in DEFAULT_NEWS_FEEDS:
            feed_tags = {str(tag).lower() for tag in feed.get("tags", [])}
            overlap = len(feed_tags & keyword_set)
            scored.append((overlap, feed))
        scored.sort(key=lambda item: (item[0], float(item[1]["authority"])), reverse=True)
        return [feed for _, feed in scored[:6]]

    def _build_news_candidate(
        self,
        entry: dict[str, Any],
        *,
        source_key: str,
        source_label: str,
        base_authority: float,
        query: str | None,
        account_keywords: list[str],
        topic_tags: list[str],
    ) -> dict[str, Any] | None:
        title = unescape(str(entry.get("title") or "")).strip()
        url = str(entry.get("url") or "").strip()
        if not title or not url:
            return None

        summary = str(entry.get("summary") or title).strip()
        published_at = entry.get("published_at")
        keyword_hits = sum(1 for keyword in account_keywords if keyword and keyword in f"{title} {summary}".lower())
        relevance_seed = 0.54 + min(0.3, keyword_hits * 0.08)
        freshness_score = self._freshness_score(published_at)
        source_name = str(entry.get("source_name") or source_label).strip() or source_label

        return {
            "title": title,
            "summary": summary,
            "source_type": "news_article",
            "source_name": source_name,
            "source_url": url,
            "published_at": published_at,
            "relevance_score": round(min(relevance_seed, 0.92), 4),
            "authority_score": round(base_authority, 4),
            "freshness_score": round(freshness_score, 4),
            "reason": (
                f"Matched the current news query{f' ({query})' if query else ''} and account-fit topic keywords."
            ),
            "topic_tags_json": self._dedupe_strings(topic_tags)[:6],
            "source_payload_json": {
                "collector": {
                    "source_key": source_key,
                    "label": source_label,
                    "kind": "news_feed",
                    "query": query,
                },
                "entry": {
                    "source_name": source_name,
                    "url": url,
                },
            },
        }

    def _build_wechat_candidate(
        self,
        entry: dict[str, Any],
        *,
        query: str,
        account_keywords: list[str],
    ) -> dict[str, Any] | None:
        title = str(entry.get("title") or "").strip()
        url = str(entry.get("url") or entry.get("intermediate_url") or "").strip()
        if not title or not url:
            return None
        summary = str(entry.get("summary") or title).strip()
        source_name = str(entry.get("source_name") or "微信公众号").strip() or "微信公众号"
        text_blob = f"{title} {summary}".lower()
        keyword_hits = sum(1 for keyword in account_keywords if keyword and keyword in text_blob)
        relevance_seed = 0.56 + min(0.28, keyword_hits * 0.08)
        published_at = entry.get("published_at") if isinstance(entry.get("published_at"), datetime) else None
        return {
            "title": title,
            "summary": summary[:400],
            "source_type": "news_article",
            "source_name": source_name,
            "source_url": url,
            "published_at": published_at,
            "relevance_score": round(min(relevance_seed, 0.9), 4),
            "authority_score": 0.58,
            "freshness_score": round(self._freshness_score(published_at), 4),
            "reason": "Matched current account-fit queries against recent WeChat article search results.",
            "topic_tags_json": self._dedupe_strings(self._tokenize(query))[:5],
            "source_payload_json": {
                "collector": {
                    "source_key": "wechat_article_search",
                    "label": "WeChat Article Search",
                    "kind": "wechat_search",
                    "query": query,
                },
                "entry": {
                    "source_name": source_name,
                    "url_resolved": bool(entry.get("url_resolved")),
                    "intermediate_url": entry.get("intermediate_url"),
                },
            },
        }

    def _parse_feed_entries(self, xml_text: str, *, default_source_name: str) -> list[dict[str, Any]]:
        # 清理无效的 Unicode 字符（如 surrogate characters）
        try:
            cleaned = bytes(xml_text, "utf-8").decode("utf-8", errors="surrogatepass")
            # 移除代理字符对
            cleaned = re.sub(r"[\ud800-\udfff]", "", cleaned)
            root = ET.fromstring(cleaned)
        except ET.ParseError as exc:
            raise ValueError(f"invalid_feed_xml: {exc}") from exc

        entries: list[dict[str, Any]] = []
        channel_items = root.findall(".//item")
        if channel_items:
            for item in channel_items:
                title = self._node_text(item, "title")
                link = self._node_text(item, "link") or self._node_text(item, "guid")
                summary = self._strip_html(self._node_text(item, "description") or "")
                pub_date = self._parse_date(self._node_text(item, "pubDate") or self._node_text(item, "published"))
                source_name = self._node_text(item, "source") or default_source_name
                entries.append(
                    {
                        "title": title,
                        "url": link,
                        "summary": summary,
                        "published_at": pub_date,
                        "source_name": source_name,
                    }
                )
            return entries

        atom_entries = [node for node in root.findall(".//*") if self._local_name(node.tag) == "entry"]
        for entry in atom_entries:
            title = self._node_text(entry, "title")
            summary = self._strip_html(
                self._node_text(entry, "summary") or self._node_text(entry, "content") or ""
            )
            link = None
            for child in entry:
                if self._local_name(child.tag) == "link":
                    href = child.attrib.get("href")
                    if href:
                        link = href
                        break
            pub_date = self._parse_date(
                self._node_text(entry, "updated")
                or self._node_text(entry, "published")
            )
            entries.append(
                {
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "published_at": pub_date,
                    "source_name": default_source_name,
                }
            )
        return entries

    def _build_account_keywords(self, *, snapshot, query_plan: dict[str, Any]) -> list[str]:
        values: list[str] = [
            str(getattr(snapshot, "positioning_summary", "") or ""),
            str(getattr(snapshot, "audience_summary", "") or ""),
            str(getattr(snapshot, "tone_summary", "") or ""),
            str(((query_plan.get("lane") or {}).get("label")) or ""),
            *[str(item) for item in (query_plan.get("search_terms") or []) if str(item).strip()],
        ]
        return self._dedupe_strings(self._tokenize(" ".join(values)))[:18]

    def _derive_topic_tags(self, query: str) -> list[str]:
        return self._dedupe_strings(self._tokenize(query))[:5]

    def _freshness_score(self, published_at: datetime | None) -> float:
        if published_at is None:
            return 0.52
        now = datetime.now(timezone.utc)
        delta_days = max((now - published_at).total_seconds() / 86400.0, 0.0)
        if delta_days <= 2:
            return 0.96
        if delta_days <= 7:
            return 0.84
        if delta_days <= 14:
            return 0.72
        if delta_days <= 30:
            return 0.56
        return 0.4

    def _parse_date(self, value: str | None) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
            if "T" in text:
                parsed = datetime.fromisoformat(text)
                return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            parsed = parsedate_to_datetime(text)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _node_text(self, node: ET.Element, local_name: str) -> str | None:
        for child in node.iter():
            if self._local_name(child.tag) == local_name:
                if child.text:
                    return child.text.strip()
        return None

    def _local_name(self, tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _strip_html(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", unescape(str(value or "")))
        text = re.sub(r"\s+", " ", text).strip()
        return text[:400]

    def _tokenize(self, value: str) -> list[str]:
        normalized = str(value or "").lower()
        normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", normalized)
        return [part.strip() for part in normalized.split(" ") if len(part.strip()) >= 2]

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)
        return deduped

    def _deduplicate_candidates(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            key = "||".join(
                [
                    str(item.get("source_type") or "").strip().lower(),
                    str(item.get("source_url") or "").strip().lower(),
                    str(item.get("title") or "").strip().lower(),
                ]
            )
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped


news_source_service = NewsSourceService()
