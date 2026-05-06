"""
Hot topic agent: analyzes hot topics relevant to the account profile.

【热点分析智能体】
从多个搜索引擎并发抓取热点，结合账号画像进行相关性分析，
输出结构化的热点话题列表。

职责分工：
- Agent 负责：根据 profile 构建关键词、调用 skill、LLM 结构化筛选
- Skill 负责：抓取、解析、归一化、去重（hot_topic_fetch_skill）
"""

from typing import Any

from app.agents.base import BaseAgent, AgentResult
from app.core.llm_gateway import llm_gateway
from app.core.logger import get_logger
from app.skills.registry import skill_registry

logger = get_logger(__name__)


class HotTopicAgent(BaseAgent):
    """
    热点分析智能体

    Agent Contract:
    - input: profile, account_context (optional), history_summary (optional)
    - output: hot_topics: list[{title, source, heat_score, summary, relevance_score}]
    - supported_skills: [hot_topic_fetch_skill]
    """

    agent_id = "hot_topic_agent"
    name = "热点分析智能体"
    description = "从多个来源抓取并分析与账号领域相关的热点"

    # Agent Contract
    input_schema = {
        "type": "object",
        "properties": {
            "profile": {
                "type": "object",
                "description": "账号画像，包含 domain、subdomain、keywords 等"
            },
            "account_context": {
                "type": "object",
                "description": "账号上下文（可选）"
            },
            "history_summary": {
                "type": "string",
                "description": "近期发布历史摘要（可选）"
            }
        },
        "required": ["profile"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "hot_topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "source": {"type": "string"},
                        "heat_score": {"type": "integer"},
                        "summary": {"type": "string"},
                        "relevance_score": {"type": "number"}
                    }
                }
            }
        }
    }

    # 该 Agent 支持调用的 Skill
    supported_skills = ["hot_topic_fetch_skill"]

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
        3. 调用 hot_topic_fetch_skill 获取原始候选
        4. LLM 分析筛选 + 结构化输出
        """
        profile = input_data.get("profile", {})
        system_prompt = context.get("system_prompt") or self.default_system_prompt

        try:
            # 1. 构建搜索关键词
            keywords = self._build_keywords(profile)

            # 2. 调用 skill 获取原始候选
            logger.info("hot_topic_skill_fetch_start", keywords=keywords)
            skill_result = await self._fetch_with_skill(keywords)
            
            if not skill_result.get("status") == "success":
                error = skill_result.get("error", {})
                raise Exception(f"Skill failed: {error.get('code', 'unknown')}")

            search_results = skill_result.get("data", {}).get("results", [])
            logger.info("hot_topic_skill_fetch_complete", results_count=len(search_results))

            if not search_results:
                return self._success({"hot_topics": []})

            # 3. LLM 分析生成结构化热点
            structured_topics = await self._analyze_with_llm(
                search_results, profile, system_prompt
            )

            return self._success({"hot_topics": structured_topics})

        except Exception as e:
            logger.error("hot_topic_agent_error", error=str(e))
            return self._failure(code="HOT_TOPIC_ERROR", message=str(e))

    def _build_keywords(self, profile: dict) -> list[str]:
        """从账号画像构建搜索关键词列表。"""
        keywords = profile.get("keywords", [])
        domain = profile.get("domain", "")

        if keywords:
            return keywords[:3]  # 最多使用前 3 个关键词
        elif domain:
            return [domain]
        return ["热点"]

    async def _fetch_with_skill(self, keywords: list[str]) -> dict:
        """调用 hot_topic_fetch_skill 获取原始候选。"""
        try:
            skill = skill_registry.get("hot_topic_fetch_skill")
            return await skill.execute({
                "keywords": keywords,
                "engines": ["weixin", "sogou", "360"],
                "max_results_per_engine": 8
            })
        except Exception as e:
            logger.warning("skill_fetch_fallback", error=str(e))
            # Skill 调用失败时返回失败结构
            return {
                "status": "failed",
                "skill_id": "hot_topic_fetch_skill",
                "data": None,
                "error": {"code": "SKILL_ERROR", "message": str(e)}
            }

    async def _analyze_with_llm(
        self, search_results: list[dict], profile: dict, system_prompt: str
    ) -> list[dict[str, Any]]:
        """
        使用 LLM 分析原始热点，生成结构化数据。

        LLM 的任务：
        1. 评估每个热点与账号领域的相关性
        2. 打分（热度 × 相关度）
        3. 排序并输出 JSON
        """
        if not search_results:
            return []

        user_prompt = self._build_analysis_prompt(search_results, profile)

        try:
            response = await llm_gateway.complete(
                agent_id=self.agent_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format="json",
            )
            data = response.parsed or {}
            return data.get("hot_topics", [])

        except Exception as e:
            logger.warning("llm_analysis_error", error=str(e))
            return self._fallback_topics(search_results)

    def _build_analysis_prompt(self, search_results: list[dict], profile: dict) -> str:
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

        for i, topic in enumerate(search_results[:15], 1):
            title = topic.get("title", "")
            source = topic.get("source", "")
            prompt_parts.append(f"{i}. [{source}] {title}")

        prompt_parts.append("")
        prompt_parts.append("请输出结构化的热点分析结果。")

        return "\n".join(prompt_parts)

    def _fallback_topics(self, search_results: list[dict]) -> list[dict[str, Any]]:
        """
        当 LLM 分析失败时，返回简化版结果。

        【Fallback 降级策略】
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
            for topic in search_results[:8]
        ]

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """
        降级策略：当 LLM 调用完全失败时。

        返回空热点列表，不中断流水线。
        后续节点（选题策划）可以处理空热点的情况。
        """
        return self._success({"hot_topics": []})
