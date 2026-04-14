"""Hot Topic Fetch Skill - 热点话题获取技能"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.logger import get_logger
from app.skills.base import BaseSkill, SkillResult

logger = get_logger(__name__)


class HotTopicFetchInput(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    max_results: int = Field(default=10, ge=1, le=50)
    sources: list[str] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    engines: list[str] = Field(default_factory=list)
    max_results_per_engine: int = Field(default=6, ge=1, le=20)


class HotTopicItem(BaseModel):
    title: str = Field()
    source: str = Field()
    source_key: str = Field()
    url: str | None = Field(default=None)
    published_at: str | None = Field(default=None)
    authority_score: float = Field(default=0.5)
    relevance_score: float = Field(default=0.5)
    snippet: str = Field(default="")
    tags: list[str] = Field(default_factory=list)


class HotTopicFetchOutput(BaseModel):
    topics: list[HotTopicItem] = Field(default_factory=list)
    total_count: int = Field(default=0)
    sources_used: list[str] = Field(default_factory=list)
    query_keywords: list[str] = Field(default_factory=list)


class HotTopicFetchSkill(BaseSkill):
    skill_id = "hot_topic_fetch_skill"
    name = "Hot Topic Fetch Skill"
    description = "从多个 RSS 源抓取热点话题，为公众号内容创作提供选题灵感"

    input_schema = HotTopicFetchInput.model_json_schema()
    output_schema = HotTopicFetchOutput.model_json_schema()

    DEFAULT_NEWS_FEEDS = [
        {"key": "ithome_rss", "label": "IT之家", "url": "https://www.ithome.com.tw/rss", "authority": 0.68, "tags": ["科技", "数码", "硬件", "软件", "ai"]},
        {"key": "openai_news", "label": "OpenAI News", "url": "https://openai.com/news/rss.xml", "authority": 0.90, "tags": ["ai", "llm", "model", "product", "developer", "tool"]},
        {"key": "techcrunch_ai", "label": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "authority": 0.76, "tags": ["ai", "startup", "product", "technology", "industry"]},
    ]

    async def execute(self, input_data: dict) -> dict:
        try:
            payload = HotTopicFetchInput(**input_data)
        except Exception as exc:
            return SkillResult.failure(skill_id=self.skill_id, code="invalid_input", message=f"输入参数错误: {exc}").to_dict()
        try:
            feeds = self.DEFAULT_NEWS_FEEDS
            if payload.sources:
                feeds = [f for f in feeds if f["key"] in payload.sources]
            keywords = list(set(payload.keywords + payload.queries))
            max_per_source = min(payload.max_results_per_engine, 10)
            topics, sources_used = await self._fetch_topics(feeds=feeds, keywords=keywords, max_per_source=max_per_source)
            if keywords:
                keywords_lower = [k.lower() for k in keywords]
                topics = [t for t in topics if any(k in t["title"].lower() or k in t.get("snippet", "").lower() for k in keywords_lower)]
            topics = topics[: payload.max_results]
            output = HotTopicFetchOutput(topics=[HotTopicItem(**t) for t in topics], total_count=len(topics), sources_used=sources_used, query_keywords=keywords)
            return SkillResult.success(skill_id=self.skill_id, data=output.model_dump()).to_dict()
        except Exception as exc:
            logger.error("hot_topic_fetch_skill_error", error=str(exc))
            return SkillResult.failure(skill_id=self.skill_id, code="fetch_error", message=str(exc)).to_dict()

    async def _fetch_topics(self, feeds, keywords, max_per_source):
        import asyncio
        import re
        from datetime import datetime
        try:
            import httpx
        except ImportError:
            return [], []
        results = []
        sources_used = []
        proxy_url = self._get_proxy_url()
        async def fetch_single_feed(feed):
            items = []
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=True, proxy=proxy_url, headers={"User-Agent": "Mozilla/5.0"}) as client:
                    response = await client.get(feed["url"])
                    response.raise_for_status()
                    items = self._parse_feed(response.text, feed, max_per_source)
            except Exception as exc:
                logger.warning("feed_fetch_failed", source=feed["key"], error=str(exc))
            return items
        feed_results = await asyncio.gather(*[fetch_single_feed(feed) for feed in feeds], return_exceptions=True)
        for feed, result in zip(feeds, feed_results):
            if isinstance(result, Exception):
                continue
            if result:
                results.extend(result)
                sources_used.append(feed["key"])
        return results, sources_used

    def _parse_feed(self, content, feed, max_items):
        import re
        results = []
        try:
            content = bytes(content, "utf-8").decode("utf-8", errors="surrogatepass")
            content = re.sub(r"[\ud800-\udfff]", "", content)
        except Exception:
            pass
        feed_key = feed["key"]
        feed_label = feed["label"]
        authority = feed["authority"]
        tags = feed.get("tags", [])
        items_rss = re.findall(r"<item>(.*?)</item>", content, re.DOTALL | re.IGNORECASE)
        items_atom = re.findall(r"<entry>(.*?)</entry>", content, re.DOTALL | re.IGNORECASE)
        items = items_rss if items_rss else items_atom
        for item in items[:max_items]:
            title_match = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
            if not title_match:
                continue
            title = self._clean_html(title_match.group(1).strip())
            link_match = re.search(r"href=[\"'](https?://[^\"']+)[\"']", item)
            if not link_match:
                link_match = re.search(r"<link(?:[^>]*)>(?:<!\[CDATA\[)?(https?://[^\s<]+)", item, re.DOTALL)
            url = link_match.group(1).strip() if link_match else ""
            desc_match = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", item, re.DOTALL)
            if not desc_match:
                desc_match = re.search(r"<summary>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</summary>", item, re.DOTALL)
            snippet = self._clean_html(desc_match.group(1).strip()[:200]) if desc_match else ""
            pub_match = re.search(r"<pubDate>(.*?)</pubDate>|<published>(.*?)</published>", item, re.DOTALL)
            published_at = None
            if pub_match:
                pub_date = pub_match.group(1) or pub_match.group(2)
                try:
                    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            dt = datetime.strptime(pub_date.strip(), fmt)
                            published_at = dt.isoformat()
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass
            if title and len(title) > 5:
                results.append({"title": title, "source": feed_label, "source_key": feed_key, "url": url or None, "published_at": published_at, "authority_score": authority, "relevance_score": 0.5, "snippet": snippet, "tags": tags})
        return results

    def _clean_html(self, text):
        import re
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _get_proxy_url(self):
        import os
        return os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")


hot_topic_fetch_skill = HotTopicFetchSkill()
