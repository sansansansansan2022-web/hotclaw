"""
Hot topic fetch skill: fetches and normalizes hot topic data from search engines.

【热点抓取技能】
从多个搜索引擎并发抓取热点，进行归一化和去重处理。

职责：
- 根据关键词抓取搜索结果
- 解析 HTML
- 归一化结果
- 去重

不负责：
- 与账号画像的最终相关性判断（由 Agent 负责）
- 最终热点排序策略（由 Agent 负责）
- LLM 结构化解释（由 Agent 负责）
"""

import asyncio
import re
from typing import Any

import httpx

from app.skills.base import BaseSkill
from app.core.logger import get_logger

logger = get_logger(__name__)


# Search engine configurations (no API key required)
SEARCH_ENGINES = [
    {
        "name": "微信搜索",
        "source": "weixin",
        "url_template": "https://wx.sogou.com/weixin?type=2&query={keyword}",
    },
    {
        "name": "搜狗搜索",
        "source": "sogou",
        "url_template": "https://sogou.com/web?query={keyword}",
    },
    {
        "name": "360搜索",
        "source": "360",
        "url_template": "https://www.so.com/s?q={keyword}",
    },
]


class HotTopicFetchSkill(BaseSkill):
    """
    Hot topic fetch skill.

    负责从多个搜索引擎抓取热点数据，返回归一化后的原始结果列表。
    """

    skill_id = "hot_topic_fetch_skill"
    name = "热点抓取技能"
    description = "从多个搜索引擎抓取热点数据，返回归一化的原始候选列表"

    # Input Schema
    input_schema = {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "搜索关键词列表，如 ['人工智能', '热点']"
            },
            "engines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "指定使用的搜索引擎，不指定则使用全部",
                "default": ["weixin", "sogou", "360"]
            },
            "max_results_per_engine": {
                "type": "integer",
                "description": "每个引擎最多返回结果数",
                "default": 8
            }
        },
        "required": ["keywords"]
    }

    # Output Schema
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
                        "snippet": {"type": "string"}
                    }
                },
                "description": "归一化后的热点列表"
            },
            "total_count": {"type": "integer"},
            "engines_used": {"type": "array", "items": {"type": "string"}}
        }
    }

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.timeout = config.get("timeout_seconds", 10) if config else 10
        self.max_results = config.get("max_results_per_engine", 8) if config else 8

    async def execute(self, input_data: dict) -> dict:
        """
        Execute the skill.

        Args:
            input_data: {
                keywords: list[str],  # 搜索关键词
                engines: list[str] | None,  # 可选，指定引擎
                max_results_per_engine: int | None,  # 可选，每引擎最多结果
            }

        Returns:
            {
                results: list[{
                    title: str,
                    source: str,
                    source_type: str,
                    url: str,
                    snippet: str
                }],
                total_count: int,
                engines_used: list[str]
            }
        """
        keywords = input_data.get("keywords", [])
        if not keywords:
            return self._failure_output("keywords_required", "keywords 参数不能为空")

        # 构建搜索关键词
        keyword = self._build_search_keyword(keywords)
        engines = input_data.get("engines", ["weixin", "sogou", "360"])
        max_results = input_data.get("max_results_per_engine", self.max_results)

        try:
            results, engines_used = await self._fetch_all_engines(keyword, engines, max_results)
            return self._success_output(results, engines_used)
        except Exception as e:
            logger.error("hot_topic_fetch_skill_error", error=str(e))
            return self._failure_output("fetch_error", str(e))

    def _build_search_keyword(self, keywords: list[str]) -> str:
        """将关键词列表转换为搜索字符串。"""
        if len(keywords) >= 2:
            search_terms = keywords[:2]
            return "+".join(search_terms) + "+热点"
        elif keywords:
            return keywords[0] + "+热点"
        return "热点"

    async def _fetch_all_engines(
        self,
        keyword: str,
        engine_names: list[str],
        max_results: int
    ) -> tuple[list[dict], list[str]]:
        """并发抓取所有指定引擎。"""
        results = []
        engines_used = []

        # 选择引擎
        engines_to_fetch = [
            e for e in SEARCH_ENGINES
            if e["source"] in engine_names
        ]

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=5.0),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        ) as client:
            tasks = []
            for engine in engines_to_fetch:
                url = engine["url_template"].format(keyword=keyword)
                tasks.append(self._fetch_engine(client, url, engine))

            engine_results = await asyncio.gather(*tasks, return_exceptions=True)

            for engine, result in zip(engines_to_fetch, engine_results):
                if isinstance(result, list) and result:
                    results.extend(result)
                    engines_used.append(engine["source"])
                elif isinstance(result, Exception):
                    logger.warning("engine_fetch_failed", engine=engine["source"], error=str(result))

        # 去重
        results = self._deduplicate(results, max_results)
        return results, engines_used

    async def _fetch_engine(
        self,
        client: httpx.AsyncClient,
        url: str,
        engine: dict
    ) -> list[dict[str, Any]]:
        """获取单个引擎的结果。"""
        try:
            response = await client.get(url)
            response.raise_for_status()

            if engine["source"] == "weixin":
                return self._parse_weixin(response.text, engine["name"])
            elif engine["source"] == "sogou":
                return self._parse_sogou(response.text, engine["name"])
            elif engine["source"] == "360":
                return self._parse_360(response.text, engine["name"])
            return []

        except Exception as e:
            logger.warning("engine_fetch_error", engine=engine["name"], error=str(e))
            return []

    def _parse_weixin(self, html: str, source: str) -> list[dict[str, Any]]:
        """解析微信搜索结果 HTML。"""
        results = []
        patterns = [
            r'<h3[^>]*class="tit"[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'class="s-p"[^>]*>.*?<a[^>]*>(.*?)</a>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                title = re.sub(r'<[^>]+>', '', match).strip()
                if title and len(title) > 5:
                    results.append({
                        "title": title,
                        "source": source,
                        "source_type": "weixin",
                        "url": "",
                        "snippet": title[:50],
                    })
        return results[:8]

    def _parse_sogou(self, html: str, source: str) -> list[dict[str, Any]]:
        """解析搜狗搜索结果 HTML。"""
        results = []
        patterns = [
            r'class="vrTitle"[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'class="pt"[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                title = re.sub(r'<[^>]+>', '', match).strip()
                if title and len(title) > 5:
                    results.append({
                        "title": title,
                        "source": source,
                        "source_type": "sogou",
                        "url": "",
                        "snippet": title[:50],
                    })
        return results[:8]

    def _parse_360(self, html: str, source: str) -> list[dict[str, Any]]:
        """解析 360 搜索结果 HTML。"""
        results = []
        patterns = [
            r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'class="res-title"[^>]*>.*?<a[^>]*>(.*?)</a>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                title = re.sub(r'<[^>]+>', '', match).strip()
                if title and len(title) > 5:
                    results.append({
                        "title": title,
                        "source": source,
                        "source_type": "360",
                        "url": "",
                        "snippet": title[:50],
                    })
        return results[:8]

    def _deduplicate(self, results: list[dict], max_total: int) -> list[dict]:
        """去重并限制总数。"""
        seen_titles = set()
        deduped = []

        for result in results:
            title = result.get("title", "").strip()
            if not title:
                continue

            # 归一化比较
            normalized = re.sub(r'[\s\W]', '', title.lower())
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
        """构建成功输出。"""
        return {
            "status": "success",
            "skill_id": self.skill_id,
            "data": {
                "results": results,
                "total_count": len(results),
                "engines_used": engines_used
            },
            "error": None
        }

    def _failure_output(self, code: str, message: str) -> dict:
        """构建失败输出。"""
        return {
            "status": "failed",
            "skill_id": self.skill_id,
            "data": None,
            "error": {"code": code, "message": message}
        }
