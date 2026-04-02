"""
Hot topic agent: analyzes hot topics relevant to the account profile.

【热点分析智能体】
从多个搜索引擎并发抓取热点，结合账号画像进行相关性分析，
输出结构化的热点话题列表。

核心流程：
1. 根据账号画像构建搜索关键词
2. 并发请求多个搜索引擎（微信/搜狗/360）
3. 正则解析 HTML 提取标题
4. LLM 分析筛选 + 结构化输出

面试点：
- asyncio.gather 并发执行
- httpx.AsyncClient 异步 HTTP
- 正则表达式 HTML 解析
- JSON 输出解析（含 markdown 代码块）
- LLM Fallback 降级策略
"""

import asyncio
import json
import re
from typing import Any

import httpx
import litellm
from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


# Search engine configurations (no API key required)
# 【搜索引擎配置】
# 这是一个轻量级的爬虫方案，不需要 API Key。
# 真实项目应使用官方 API（如微信搜一搜 API）。
SEARCH_ENGINES = [
    {
        "name": "微信搜索",
        "source": "微信搜索",
        "url_template": "https://wx.sogou.com/weixin?type=2&query={keyword}",
    },
    {
        "name": "搜狗搜索",
        "source": "搜狗",
        "url_template": "https://sogou.com/web?query={keyword}",
    },
    {
        "name": "360搜索",
        "source": "360搜索",
        "url_template": "https://www.so.com/s?q={keyword}",
    },
]


class HotTopicAgent(BaseAgent):
    """热点分析智能体"""

    agent_id = "hot_topic_agent"
    name = "热点分析智能体"
    description = "从多个来源抓取并分析与账号领域相关的热点"

    default_system_prompt = """\
你是一位精通中文互联网生态的热点分析师，能够从海量信息中筛选出与特定账号领域高度相关的热点话题。

## 任务
根据账号画像（profile）和搜索结果，筛选与账号领域相关的热点话题。

## 输入
- profile (object): 账号画像数据，包含 domain、subdomain、target_audience、tone 等字段
- search_results (array): 从多个搜索引擎抓取的原始搜索结果

## 输出要求
必须输出 JSON 对象，包含：
- hot_topics (array): 5-8 条热点，每条包含：
  - title (string): 热点标题
  - source (string): 来源平台（微信搜索/搜狗/360搜索等）
  - heat_score (int): 热度评分 0-100
  - summary (string): 热点摘要，50字以内
  - relevance_score (float): 与账号领域的相关度 0-1

## 约束
- 只选择与账号领域确实相关的热点，relevance_score 低于 0.5 的不要纳入
- 按 heat_score * relevance_score 降序排列
- 热点来源需多样化，不要全部来自同一平台
- 摘要需客观精炼，不加主观判断"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """
        执行热点分析。

        工作流程：
        1. 从 input_data 获取账号画像
        2. 构建搜索关键词
        3. 并发抓取多引擎搜索结果
        4. 正则解析 HTML 提取标题
        5. LLM 分析筛选 + 结构化输出
        """
        profile = input_data.get("profile", {})
        system_prompt = context.get("system_prompt") or self.default_system_prompt

        try:
            # 1. 构建搜索关键词
            search_keyword = self._build_search_keyword(profile)

            # 2. 多引擎搜索
            logger.info("hot_topic_search_start", keyword=search_keyword)
            search_results = await self._multi_engine_search(search_keyword)
            logger.info("hot_topic_search_complete", results_count=len(search_results))

            # 3. 提取热点
            raw_topics = self._extract_topics(search_results)
            logger.info("hot_topic_extracted", topics_count=len(raw_topics))

            # 4. LLM 分析生成结构化热点
            structured_topics = await self._analyze_with_llm(
                raw_topics, profile, system_prompt
            )

            return self._success({"hot_topics": structured_topics})

        except Exception as e:
            logger.error("hot_topic_agent_error", error=str(e))
            return self._failure(code="HOT_TOPIC_ERROR", message=str(e))

    def _build_search_keyword(self, profile: dict) -> str:
        """
        根据账号画像构建搜索关键词。

        策略：优先使用关键词，次用领域名称。
        """
        domain = profile.get("domain", "")
        keywords = profile.get("keywords", [])

        if keywords:
            # 使用前两个关键词 + "热点"
            search_terms = keywords[:2]
            search_keyword = "+".join(search_terms) + "+热点"
        else:
            search_keyword = domain + "+热点"

        return search_keyword

    async def _multi_engine_search(self, keyword: str) -> list[dict[str, Any]]:
        """
        多引擎并发搜索。

        【核心】asyncio.gather 实现并发
        所有搜索引擎同时请求，大幅减少总等待时间。
        return_exceptions=True 确保一个引擎失败不影响其他引擎。
        """
        results = []

        async with httpx.AsyncClient(
            # 超时配置：单个请求最多 10 秒，连接建立最多 5 秒
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True,
            headers={
                # 模拟浏览器 User-Agent，避免被反爬
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        ) as client:
            # 构建所有引擎的抓取任务
            tasks = []
            for engine in SEARCH_ENGINES:
                url = engine["url_template"].format(keyword=keyword)
                tasks.append(self._fetch_engine(client, url, engine))

            # 【并发执行】所有引擎同时抓取
            engine_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 合并所有引擎的结果
            for result in engine_results:
                if isinstance(result, list):
                    results.extend(result)

        return results

    async def _fetch_engine(
        self, client: httpx.AsyncClient, url: str, engine: dict
    ) -> list[dict[str, Any]]:
        """获取单个搜索引擎的结果。"""
        try:
            response = await client.get(url)
            response.raise_for_status()

            # 根据不同引擎调用对应的解析方法
            if engine["source"] == "微信搜索":
                return self._parse_weixin(response.text, engine["source"])
            elif engine["source"] == "搜狗":
                return self._parse_sogou(response.text, engine["source"])
            elif engine["source"] == "360搜索":
                return self._parse_360(response.text, engine["source"])
            else:
                return []

        except Exception as e:
            logger.warning("engine_fetch_error", engine=engine["source"], error=str(e))
            return []

    def _parse_weixin(self, html: str, source: str) -> list[dict[str, Any]]:
        """解析微信搜索结果 HTML。"""
        results = []

        # 微信搜索结果的标题通常在这些 CSS 类中
        patterns = [
            r'<h3[^>]*class="tit"[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'class="s-p"[^>]*>.*?<a[^>]*>(.*?)</a>',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                # 清理 HTML 标签，只保留纯文本
                title = re.sub(r'<[^>]+>', '', match).strip()
                if title and len(title) > 5:
                    results.append({
                        "title": title,
                        "source": source,
                        "url": "",
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
                        "url": "",
                    })

        return results[:8]

    def _parse_360(self, html: str, source: str) -> list[dict[str, Any]]:
        """解析 360 搜索结果 HTML。"""
        results = []

        patterns = [
            r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'class="res-title"[^>]*>.*?<a[^>]*>(.*?)</a>',
            r'data-url="[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                title = re.sub(r'<[^>]+>', '', match).strip()
                if title and len(title) > 5:
                    results.append({
                        "title": title,
                        "source": source,
                        "url": "",
                    })

        return results[:8]

    def _extract_topics(self, search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        从搜索结果中提取并去重热点。

        去重策略：归一化标题（去除空格和标点）进行比较。
        """
        seen_titles = set()
        topics = []

        for result in search_results:
            title = result.get("title", "").strip()

            # 归一化：去除空格和非字母数字字符
            normalized = re.sub(r'[\s\W]', '', title.lower())
            if normalized in seen_titles:
                continue

            # 过滤无效标题
            if len(title) < 5 or len(title) > 100:
                continue

            seen_titles.add(normalized)
            topics.append({
                "title": title,
                "source": result.get("source", "未知"),
                "url": result.get("url", ""),
            })

        return topics

    async def _analyze_with_llm(
        self, raw_topics: list[dict[str, Any]], profile: dict, system_prompt: str
    ) -> list[dict[str, Any]]:
        """
        使用 LLM 分析原始热点，生成结构化数据。

        LLM 的任务：
        1. 评估每个热点与账号领域的相关性
        2. 打分（热度 × 相关度）
        3. 排序并输出 JSON
        """
        if not raw_topics:
            return []

        user_prompt = self._build_analysis_prompt(raw_topics, profile)

        try:
            model = settings.llm_model_name
            if not model.startswith("dashscope/"):
                model = f"dashscope/{model}"

            response = await litellm.acompletion(
                model=model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base_url,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=settings.llm_timeout,
                custom_llm_provider="dashscope",
            )
            content = response.choices[0].message.content

            # 解析 JSON（处理 markdown 代码块）
            data = self._parse_json(content)
            return data.get("hot_topics", [])

        except json.JSONDecodeError as e:
            logger.warning("llm_json_parse_error", error=str(e))
            return self._fallback_topics(raw_topics)
        except Exception as e:
            logger.warning("llm_analysis_error", error=str(e))
            return self._fallback_topics(raw_topics)

    def _build_analysis_prompt(self, raw_topics: list[dict[str, Any]], profile: dict) -> str:
        """构建 LLM 分析提示词。"""
        domain = profile.get("domain", "未知")
        subdomain = profile.get("subdomain", "")
        keywords = profile.get("keywords", [])

        prompt_parts = [
            "请分析以下搜索结果，筛选出与账号领域相关的热点话题。",
            "",
            "## 账号信息",
            f"- 主领域: {domain}",
            f"- 细分领域: {subdomain}",
        ]

        if keywords:
            prompt_parts.append(f"- 关键词: {', '.join(keywords)}")

        prompt_parts.append("")
        prompt_parts.append("## 搜索结果（来自多引擎）")

        for i, topic in enumerate(raw_topics[:15], 1):
            title = topic.get("title", "")
            source = topic.get("source", "")
            prompt_parts.append(f"{i}. [{source}] {title}")

        prompt_parts.append("")
        prompt_parts.append("请输出结构化的热点分析结果。")

        return "\n".join(prompt_parts)

    def _fallback_topics(self, raw_topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        当 LLM 分析失败时，返回简化版结果。

        【Fallback 降级策略】
        如果 LLM 调用失败（网络问题、解析错误等），
        使用预设的默认值返回部分结果，避免整个流程中断。
        """
        return [
            {
                "title": topic.get("title", ""),
                "source": topic.get("source", ""),
                "heat_score": 70,  # 默认热度
                "summary": topic.get("title", "")[:50],
                "relevance_score": 0.6,
            }
            for topic in raw_topics[:8]
        ]

    def _parse_json(self, content: str) -> dict:
        """
        解析 LLM 返回的 JSON。

        LLM 返回的格式可能是：
        1. 纯 JSON：{"hot_topics": [...]}
        2. Markdown 代码块：```json\n{...}\n```
        """
        content = content.strip()
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
        return json.loads(content)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """
        降级策略：当 LLM 调用完全失败时。

        返回空热点列表，不中断流水线。
        后续节点（选题策划）可以处理空热点的情况。
        """
        return self._success({"hot_topics": []})
