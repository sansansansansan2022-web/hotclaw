"""Native WeChat article search service adapted from external search workflow."""

from __future__ import annotations

import random
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalAPIError
from app.core.logger import get_logger

logger = get_logger(__name__)

WECHAT_SEARCH_HOST = "https://weixin.sogou.com"
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
)


class WechatArticleSearchService:
    """Search and normalize WeChat article candidates from Sogou Weixin search."""

    def __init__(self) -> None:
        self.timeout = max(int(getattr(settings, "wechat_article_search_timeout_seconds", 15) or 15), 5)

    def _get_proxy_url(self) -> str | None:
        import os

        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if http_proxy:
            return http_proxy
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        return https_proxy

    async def search_articles(
        self,
        *,
        query: str,
        max_results: int = 10,
        resolve_real_urls: bool = False,
    ) -> list[dict[str, Any]]:
        clean_query = str(query or "").strip()
        if not clean_query:
            raise ValueError("query is required")
        limit = max(1, min(int(max_results or 10), 50))

        cookies = await self._bootstrap_cookies()
        articles: list[dict[str, Any]] = []
        pages_needed = max(1, min((limit + 9) // 10, 5))

        async with self._client() as client:
            for page in range(1, pages_needed + 1):
                html = await self._fetch_search_page(client, query=clean_query, page=page, cookie_header=cookies)
                articles.extend(self._parse_search_html(html, remaining=limit - len(articles)))
                if len(articles) >= limit:
                    break

            if resolve_real_urls:
                resolved: list[dict[str, Any]] = []
                for article in articles:
                    resolved.append(await self._resolve_article_url(client, article, cookies))
                articles = resolved

        return articles[:limit]

    async def _bootstrap_cookies(self) -> str:
        try:
            async with self._client() as client:
                response = await client.get("https://v.sogou.com/v?ie=utf8&query=&p=40030600")
        except Exception:
            return ""
        cookie_pairs: list[str] = []
        for cookie in response.cookies.jar:
            if cookie.name and cookie.value:
                cookie_pairs.append(f"{cookie.name}={cookie.value}")
        return "; ".join(cookie_pairs)

    async def _fetch_search_page(
        self,
        client: httpx.AsyncClient,
        *,
        query: str,
        page: int,
        cookie_header: str,
    ) -> str:
        url = (
            f"{WECHAT_SEARCH_HOST}/weixin?query={quote(query)}&s_from=input&_sug_=n"
            f"&type=2&page={page}&ie=utf8"
        )
        headers = self._headers(cookie_header)
        try:
            response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ExternalAPIError("WeChat article search timed out", details={"query": query, "page": page}) from exc
        except httpx.HTTPError as exc:
            raise ExternalAPIError("WeChat article search failed", details={"query": query, "page": page}) from exc
        if response.status_code >= 400:
            raise ExternalAPIError(
                "WeChat article search failed",
                details={"query": query, "page": page, "status_code": response.status_code},
            )
        return response.text

    def _parse_search_html(self, html: str, *, remaining: int) -> list[dict[str, Any]]:
        if remaining <= 0:
            return []
        news_list_match = re.search(r'(?is)<ul[^>]*class="[^"]*news-list[^"]*"[^>]*>(.*?)</ul>', html)
        if not news_list_match:
            return []
        items_html = re.findall(r"(?is)<li\b.*?>.*?</li>", news_list_match.group(1))
        rows: list[dict[str, Any]] = []
        for item_html in items_html:
            article = self._parse_article_item(item_html)
            if article:
                rows.append(article)
            if len(rows) >= remaining:
                break
        return rows

    def _parse_article_item(self, item_html: str) -> dict[str, Any] | None:
        title_match = re.search(r'(?is)<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', item_html)
        if not title_match:
            return None
        href = title_match.group(1).strip()
        title = self._strip_html(title_match.group(2))
        if not title:
            return None

        summary_match = re.search(r'(?is)<p[^>]*class="[^"]*txt-info[^"]*"[^>]*>(.*?)</p>', item_html)
        summary = self._strip_html(summary_match.group(1)) if summary_match else ""

        source_match = re.search(r'(?is)<a[^>]*class="[^"]*account[^"]*"[^>]*>(.*?)</a>', item_html)
        if not source_match:
            source_match = re.search(r'(?is)<span[^>]*class="[^"]*all-time-y2[^"]*"[^>]*>(.*?)</span>', item_html)
        source_name = self._strip_html(source_match.group(1)) if source_match else "微信公众号"

        published_at = None
        timestamp_match = re.search(r"(?<!\d)(1\d{9})(?!\d)", item_html)
        if timestamp_match:
            try:
                published_at = datetime.fromtimestamp(int(timestamp_match.group(1)), tz=timezone.utc)
            except (OSError, ValueError):
                published_at = None

        normalized_url = href
        if normalized_url.startswith("/"):
            normalized_url = f"{WECHAT_SEARCH_HOST}{normalized_url}"

        return {
            "title": title,
            "summary": summary[:400],
            "url": normalized_url,
            "intermediate_url": normalized_url,
            "source_name": source_name,
            "published_at": published_at,
            "url_resolved": False,
        }

    async def _resolve_article_url(
        self,
        client: httpx.AsyncClient,
        article: dict[str, Any],
        cookie_header: str,
    ) -> dict[str, Any]:
        url = str(article.get("intermediate_url") or article.get("url") or "").strip()
        if not url or "weixin.sogou.com" not in url:
            article["url_resolved"] = True
            return article
        try:
            response = await client.get(url, headers=self._headers(cookie_header), follow_redirects=False)
        except Exception:
            return article

        location = response.headers.get("location")
        if location and "mp.weixin.qq.com" in location:
            article["url"] = location
            article["url_resolved"] = True
            return article

        redirect_url = self._extract_redirect_url(response.text)
        if redirect_url and "mp.weixin.qq.com" in redirect_url:
            article["url"] = redirect_url
            article["url_resolved"] = True
        return article

    def _extract_redirect_url(self, html: str) -> str | None:
        meta_match = re.search(
            r'(?is)<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\']\d+;\s*url=([^"\']+)["\']',
            html,
        )
        if meta_match:
            return meta_match.group(1).strip()
        for pattern in (
            r'location\.href\s*=\s*["\']([^"\']+)["\']',
            r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']',
            r'location\.replace\(["\']([^"\']+)["\']\)',
        ):
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()
        parts = [match.group(1) for match in re.finditer(r"url\s*\+=\s*['\"]([^'\"]+)['\"]", html)]
        if parts:
            return "".join(parts)
        return None

    def _headers(self, cookie_header: str = "") -> dict[str, str]:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "identity",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Host": "weixin.sogou.com",
            "Referer": "https://weixin.sogou.com/",
            "User-Agent": random.choice(USER_AGENTS),
        }
        if cookie_header:
            headers["Cookie"] = cookie_header
        return headers

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(8.0, float(self.timeout))),
            headers={"User-Agent": random.choice(USER_AGENTS)},
            proxy=self._get_proxy_url(),
            trust_env=False,
        )

    def _strip_html(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", unescape(str(value or "")))
        text = re.sub(r"\s+", " ", text).strip()
        return text


wechat_article_search_service = WechatArticleSearchService()
