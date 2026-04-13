"""Title generator agent for source-backed topic candidates."""

# ============================================================================
# 标题生成 Agent (Title Generator Agent)
# ============================================================================
# 职责说明：
# - 为选定的话题候选生成多个标题选项
# - 从多个话题中挑选最具吸引力的一个
# - 生成风格多样的标题（直接型、悬念型、情感型等）
# - 为每个标题评分并说明理由
# - 确保标题有吸引力但不夸大
#
# 协作关系：
# - 输入：话题候选 (TopicPlannerAgent)、账号画像、证据
# - 输出：选中的话题 + 标题候选列表（带评分和风格）
# - 为 ContentWriterAgent 提供标题输入
# ============================================================================

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service


class TitleGeneratorAgent(BaseAgent):
    """标题生成 Agent - 为话题生成吸引人的标题选项。

    核心职责：
    1. 分析并选择最具吸引力的话题候选
    2. 生成 4-6 个风格多样的标题
    3. 为每个标题评分并说明选择理由
    4. 确保标题与账号风格和证据一致
    5. 避免空洞的标题党

    特点：
    - 强调标题的可信度和吸引力平衡
    - 风格多样性但不偏离话题
    - 基于证据生成，禁止虚构论文/项目名
    """

    # Agent 唯一标识符
    agent_id = "title_generator_agent"
    name = "Title Generator"
    description = "Generate title candidates grounded in strategy and reference cues."

    # 输入数据结构定义
    # profile: 账号画像
    # topics: 话题候选列表（必需）
    # account_context: 账号上下文
    # ops_context: 运营上下文
    # query_plan: 查询计划
    # reference_digest: 参考摘要
    # source_candidates: 来源候选
    # selected_evidence: 选中的证据
    # evidence_summaries: 证据摘要
    # citation_guardrails: 引用规范
    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "topics": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["profile", "topics"],
    }

    # 输出数据结构定义
    # selected_topic: 选中的话题标题
    # titles: 标题候选列表
    # 每个标题包含：文本、风格、评分、推理说明
    output_schema = {
        "type": "object",
        "properties": {
            "selected_topic": {"type": "string"},
            "titles": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "style": {"type": "string"},
                        "score": {"type": "number"},
                        "reasoning": {"type": "string"},
                    },
                },
            },
        },
    }

    # 默认系统提示词
    default_system_prompt = """You are a WeChat title strategist.

Choose the strongest topic candidate and generate 4-6 titles that feel click-worthy without losing credibility.
Return strict JSON only.

Rules:
- Titles must reflect the chosen topic package, account voice, and source-backed angle.
- Avoid empty shock-value or titles that could belong to any account.
- Show style diversity, but keep the title promises compatible with the outline the team will later write.
- Do not invent specific paper names or repo names that are absent from the evidence list.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """执行标题生成。

        主要步骤：
        1. 获取系统提示词和构建用户提示词
        2. 调用 LLM 生成标题
        3. 规范化输出格式
        4. 返回选中的话题和标题列表

        Args:
            input_data: 包含话题、账号画像等的输入数据
            context: 执行上下文

        Returns:
            AgentResult: 包含选中话题和标题候选列表
        """
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

        try:
            # 调用 LLM 生成标题
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
            return self._success(self._normalize_titles(self._parse_json(content), input_data))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse title JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """LLM 调用失败时的降级处理。

        选择评分最高的话题，
        直接使用话题标题作为唯一标题选项。

        Args:
            error: 发生的异常
            input_data: 原始输入数据

        Returns:
            AgentResult: 基于话题标题的简化标题
        """
        # 选择评分最高的话题
        selected_topic = self._pick_topic(input_data.get("topics") or {})
        return self._success(
            {
                "selected_topic": selected_topic,
                "titles": [
                    {
                        "text": selected_topic or "Untitled",
                        "style": "direct",
                        "score": 5.0,
                        "reasoning": "Fallback uses the strongest topic title directly.",
                    }
                ],
            }
        )

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        """构建 LLM 用户提示词。

        整合账号快照、话题、证据等信息，
        生成完整标题生成指令。

        Args:
            input_data: 原始输入数据

        Returns:
            str: 完整的用户提示词
        """
        profile = input_data.get("profile") or {}
        topics = input_data.get("topics") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        query_plan = input_data.get("query_plan")
        # 如果没有查询计划则构建
        if not isinstance(query_plan, dict):
            query_plan = query_planner_service.build_plan(
                profile=profile,
                account_context=account_context,
                ops_context=ops_context,
            )
        reference_digest = input_data.get("reference_digest") or {}
        selected_evidence = input_data.get("selected_evidence") or []
        evidence_summaries = input_data.get("evidence_summaries") or {}

        # 获取排序后的前 3 个话题
        sorted_topics = self._sorted_topics(topics)
        topic_package = sorted_topics[:3]

        # 构建账号快照
        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
        }

        return "\n".join(
            [
                "Generate title candidates for the strongest topic package.",
                "",
                "ACCOUNT SNAPSHOT",
                article_assembler_service.to_pretty_json(account_snapshot),
                "",
                "QUERY PLAN",
                article_assembler_service.to_pretty_json(query_plan),
                "",
                "REFERENCE DIGEST",
                article_assembler_service.to_pretty_json(reference_digest),
                "",
                "EVIDENCE SUMMARIES",
                article_assembler_service.to_pretty_json(evidence_summaries),
                "",
                "SELECTED EVIDENCE",
                article_assembler_service.to_pretty_json(selected_evidence[:8] if isinstance(selected_evidence, list) else []),
                "",
                "TOPIC CANDIDATES",
                article_assembler_service.to_pretty_json(topic_package),
                "",
                "RETURN CONTRACT",
                "- Return JSON with selected_topic and titles.",
                "- titles must include text, style, score, reasoning.",
                "- Generate 4-6 options with real style diversity, but keep them consistent with the chosen topic package.",
                "- If a title mentions a paper or repository by name, that name must appear in SELECTED EVIDENCE.",
            ]
        )

    def _sorted_topics(self, topics: dict[str, Any]) -> list[dict[str, Any]]:
        """对话题列表按吸引力评分排序。

        Args:
            topics: 包含话题列表的字典

        Returns:
            list[dict]: 按评分降序排列的话题列表
        """
        items = topics.get("topics") if isinstance(topics.get("topics"), list) else []
        normalized = [item for item in items if isinstance(item, dict)]
        # 按吸引力评分降序排列
        normalized.sort(key=lambda item: float(item.get("estimated_appeal") or 0.0), reverse=True)
        return normalized

    def _pick_topic(self, topics: dict[str, Any]) -> str:
        """选择评分最高的话题标题。

        Args:
            topics: 包含话题列表的字典

        Returns:
            str: 评分最高的话题标题
        """
        sorted_topics = self._sorted_topics(topics)
        if sorted_topics:
            return str(sorted_topics[0].get("title") or "").strip()
        return ""

    def _normalize_titles(self, data: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        """规范化标题列表。

        确保每个标题包含所有必需字段，
        处理可能的格式错误。

        Args:
            data: LLM 返回的原始数据
            input_data: 原始输入数据（用于降级）

        Returns:
            dict: 规范化后的标题列表和选中话题
        """
        # 确定选中的话题
        selected_topic = str(data.get("selected_topic") or self._pick_topic(input_data.get("topics") or {})).strip()
        raw_titles = data.get("titles") if isinstance(data, dict) else None
        normalized_titles: list[dict[str, Any]] = []
        if isinstance(raw_titles, list):
            for item in raw_titles:
                if not isinstance(item, dict):
                    continue
                # 支持 text 或 title 字段
                text = str(item.get("text") or item.get("title") or "").strip()
                if not text:
                    continue
                normalized_titles.append(
                    {
                        "text": text,
                        "style": str(item.get("style") or "").strip(),
                        "score": float(item.get("score") or 0.0),
                        "reasoning": str(item.get("reasoning") or "").strip(),
                    }
                )
        return {
            "selected_topic": selected_topic,
            "titles": normalized_titles,
        }

    def _parse_json(self, content: str) -> dict[str, Any]:
        """解析 LLM 返回的 JSON 内容。

        处理可能包含 markdown 代码块的格式。

        Args:
            content: LLM 返回的原始文本

        Returns:
            dict: 解析后的数据字典
        """
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)
