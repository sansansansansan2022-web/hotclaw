"""热点话题获取 Skill 入口脚本"""
from __future__ import annotations

# Windows UTF-8 输出兼容（必须在 from __future__ 之后）
import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import asyncio
import json
import re
import sys as _sys
import warnings
from datetime import datetime
from typing import Any

warnings.filterwarnings("ignore")

try:
    import httpx
except ImportError:
    print("需要安装 httpx: pip install httpx", file=_sys.stderr)
    _sys.exit(1)


def get_proxy_url() -> str | None:
    """Get HTTP proxy URL from environment variables."""
    import os
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if http_proxy:
        return http_proxy
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return https_proxy

# 默认 RSS 数据源配置
DEFAULT_NEWS_FEEDS: list[dict[str, Any]] = [
    # 国内可达源
    {
        "key": "zhihu_rss",
        "label": "知乎 RSS",
        "url": "https://www.zhihu.com/rss",
        "authority": 0.70,
        "tags": ["科技", "ai", "产品", "创业", "商业", "互联网"],
    },
    {
        "key": "36kr_rss",
        "label": "36Kr",
        "url": "https://36kr.com/feed",
        "authority": 0.72,
        "tags": ["创业", "科技", "投资", "商业", "ai"],
    },
    {
        "key": "ithome_rss",
        "label": "IT之家",
        "url": "https://www.ithome.com.tw/rss",
        "authority": 0.68,
        "tags": ["科技", "数码", "硬件", "软件", "ai"],
    },
    # 海外可达源
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
]

TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class HotTopicFetcher:
    """热点话题抓取器"""

    def __init__(
        self,
        feeds: list[dict[str, Any]] | None = None,
        timeout: httpx.Timeout | None = None,
    ):
        self.feeds = feeds or DEFAULT_NEWS_FEEDS
        self.timeout = timeout or TIMEOUT

    async def fetch_all(self) -> dict[str, Any]:
        """抓取所有数据源的热点"""
        results: list[dict[str, Any]] = []
        sources_used: list[str] = []

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            proxy=get_proxy_url(),
        ) as client:
            tasks = [self._fetch_feed(client, feed) for feed in self.feeds]
            feed_results = await asyncio.gather(*tasks, return_exceptions=True)

        for feed, result in zip(self.feeds, feed_results):
            if isinstance(result, Exception):
                print(f"[WARN] Failed to fetch {feed['key']}: {result}", file=sys.stderr)
                continue
            if result:
                results.extend(result)
                sources_used.append(feed["key"])

        return {
            "topics": results,
            "total_count": len(results),
            "sources_used": sources_used,
        }

    async def _fetch_feed(
        self,
        client: httpx.AsyncClient,
        feed: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """抓取单个 RSS 源"""
        try:
            response = await client.get(feed["url"])
            response.raise_for_status()
            content = response.text

            # 解析 RSS/Atom 格式
            items = self._parse_feed(content, feed)
            return items
        except Exception as e:
            print(f"[ERROR] {feed['key']}: {e}", file=sys.stderr)
            return []

    def _parse_feed(
        self,
        content: str,
        feed: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """解析 RSS/Atom 内容"""
        results: list[dict[str, Any]] = []

        # 简单 RSS 解析（适配大多数 RSS 2.0 和 Atom 格式）
        import re

        feed_key = feed["key"]
        feed_label = feed["label"]
        authority = feed["authority"]
        tags = feed.get("tags", [])

        # RSS 2.0 格式
        items_rss = re.findall(
            r"<item>(.*?)</item>",
            content,
            re.DOTALL | re.IGNORECASE,
        )

        # Atom 格式
        items_atom = re.findall(
            r"<entry>(.*?)</entry>",
            content,
            re.DOTALL | re.IGNORECASE,
        )

        items = items_rss if items_rss else items_atom

        for item in items[:10]:  # 限制每个源最多 10 条
            # 提取标题
            title_match = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.DOTALL)
            if not title_match:
                continue
            title = self._clean_html(title_match.group(1).strip())

            # 提取链接
            link_match = re.search(r"<link(?:[^>]*)>(?:<!\[CDATA\[)?(https?://[^\s<]+)", item, re.DOTALL)
            if not link_match:
                link_match = re.search(r"href=[\"'](https?://[^\"']+)[\"']", item)
            url = link_match.group(1).strip() if link_match else ""

            # 提取描述/摘要
            desc_match = re.search(
                r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>",
                item,
                re.DOTALL,
            )
            if not desc_match:
                desc_match = re.search(
                    r"<summary>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</summary>",
                    item,
                    re.DOTALL,
                )
            snippet = self._clean_html(desc_match.group(1).strip()[:200]) if desc_match else ""

            # 提取发布时间
            pub_match = re.search(
                r"<pubDate>(.*?)</pubDate>|<published>(.*?)</published>",
                item,
                re.DOTALL,
            )
            published_at = ""
            if pub_match:
                pub_date = pub_match.group(1) or pub_match.group(2)
                try:
                    # 尝试解析常见日期格式
                    for fmt in [
                        "%a, %d %b %Y %H:%M:%S %z",
                        "%Y-%m-%dT%H:%M:%S%z",
                        "%Y-%m-%d %H:%M:%S",
                    ]:
                        try:
                            dt = datetime.strptime(pub_date.strip(), fmt)
                            published_at = dt.isoformat()
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            if title and len(title) > 5:
                results.append({
                    "title": title,
                    "source": feed_label,
                    "source_key": feed_key,
                    "url": url,
                    "published_at": published_at,
                    "authority_score": authority,
                    "snippet": snippet,
                    "tags": tags,
                })

        return results

    def _clean_html(self, text: str) -> str:
        """清理 HTML 标签"""
        import re

        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)
        # 移除多余空白
        text = re.sub(r"\s+", " ", text)
        return text.strip()


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    """异步主函数"""
    # 筛选指定的数据源
    feeds = None
    if args.sources:
        source_keys = [s.strip() for s in args.sources.split(",")]
        feeds = [f for f in DEFAULT_NEWS_FEEDS if f["key"] in source_keys]
        if not feeds:
            return {
                "status": "error",
                "error": {
                    "code": "invalid_sources",
                    "message": f"未找到指定的数据源: {args.sources}",
                },
            }

    fetcher = HotTopicFetcher(feeds=feeds)
    result = await fetcher.fetch_all()

    # 按关键词过滤（如果指定）
    if args.keywords:
        keywords = [k.lower() for k in args.keywords]
        result["topics"] = [
            t for t in result["topics"]
            if any(k in t["title"].lower() or k in t.get("snippet", "").lower() for k in keywords)
        ]
        result["total_count"] = len(result["topics"])

    # 限制结果数量
    if args.max_results:
        result["topics"] = result["topics"][:args.max_results]
        result["total_count"] = len(result["topics"])

    return {
        "status": "success",
        "data": result,
    }


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="热点话题获取工具")
    parser.add_argument(
        "--keywords",
        nargs="+",
        help="关键词列表，用于筛选相关内容",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="最大返回结果数",
    )
    parser.add_argument(
        "--sources",
        type=str,
        help="指定数据源，用逗号分隔（如: 36kr_rss,zhihu_rss）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式",
    )

    args = parser.parse_args()

    result = asyncio.run(main_async(args))

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["status"] == "success":
            print(f"✅ 获取到 {result['data']['total_count']} 条热点")
            print(f"📡 数据源: {', '.join(result['data']['sources_used'])}")
            print()
            for i, topic in enumerate(result["data"]["topics"], 1):
                print(f"{i}. [{topic['source']}] {topic['title']}")
                if topic.get("url"):
                    print(f"   🔗 {topic['url']}")
                print()
        else:
            print(f"错误: {result['error']['message']}", file=_sys.stderr)
            _sys.exit(1)


if __name__ == "__main__":
    main()
