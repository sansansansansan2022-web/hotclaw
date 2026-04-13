"""Topic planner agent for account-aware content strategy."""

# ============================================================================
# 话题规划 Agent (Topic Planner Agent)
# ============================================================================
# 职责说明：
# - 基于热点话题生成适合账号定位的话题候选
# - 为每个话题候选设计独特的切入角度和写作策略
# - 决定话题类型（论文摘要、研究趋势、项目评测等）
# - 生成有吸引力的钩子（hook）和情感定位
#
# 协作关系：
# - 输入：热点话题 (HotTopicAgent)、账号画像、引用证据
# - 输出：话题候选列表（带角度、钩子、情感定位等）
# - 为 TitleGeneratorAgent 提供话题输入
# ============================================================================

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service


class TopicPlannerAgent(BaseAgent):
    """话题规划 Agent - 将热点话题转换为账号专属的话题候选。

    核心职责：
    1. 分析热点话题与账号定位的匹配度
    2. 为每个话题设计独特的切入角度
    3. 确定话题类型（paper_digest、github_project_review 等）
    4. 设计情感钩子和目标读者定位
    5. 关联引用证据作为话题支撑

    特点：
    - 不只是复述热点，而是转化为账号能"拥有"的话题
    - 强调时效性和可写性的平衡
    - 支持多种话题类型，覆盖不同内容形式
    """

    # Agent 唯一标识符
    agent_id = "topic_planner_agent"
    name = "Topic Planner"
    description = "Turn source-backed hot topics into account-fit topic candidates."

    # 输入数据结构定义
    # profile: 账号画像（必需）
    # hot_topics: 热点话题列表（必需）
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
            "hot_topics": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["profile", "hot_topics"],
    }

    # 输出数据结构定义
    # topics: 话题候选列表
    # 每个话题包含：标题、角度、钩子、情感定位、吸引力评分、推理过程、
    # 时效性理由、引用基础、目标读者、内容赛道、话题类型、证据引用
    output_schema = {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "angle": {"type": "string"},
                        "hook": {"type": "string"},
                        "target_emotion": {"type": "string"},
                        "estimated_appeal": {"type": "number"},
                        "reasoning": {"type": "string"},
                        "why_now": {"type": "string"},
                        "reference_basis": {"type": "string"},
                        "target_reader": {"type": "string"},
                        "content_lane": {"type": "string"},
                        "topic_kind": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }

    # 默认系统提示词
    default_system_prompt = """You are a senior WeChat content strategist.

Turn source-backed hot topics into 3-5 topic candidates that this account can actually own.
Return strict JSON only.

Rules:
- Topic candidates must be account-fit, source-backed, and audience-aware.
- Do not just restate a hot topic. Choose a sharper angle the account can credibly write.
- Explain why each topic is worth writing now, which reference basis supports it, and who it is really for.
- Avoid generic lane drift, shallow summaries, and topics that duplicate the recent-avoid list.
- topic_kind must be one of: paper_digest, research_trend, github_project_review, tools_roundup, benchmark_analysis, industry_method_explainer, general_analysis.
- When external evidence exists, evidence_refs must name the real paper or repo titles that support the topic.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """执行话题规划。

        主要步骤：
        1. 获取系统提示词和构建用户提示词
        2. 调用 LLM 生成话题候选
        3. 规范化输出格式
        4. 返回话题列表

        Args:
            input_data: 包含热点话题、账号画像等的输入数据
            context: 执行上下文

        Returns:
            AgentResult: 包含话题候选列表
        """
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

        try:
            # 调用 LLM 生成话题
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
            return self._success(self._normalize_topics(self._parse_json(content)))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse topic JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """LLM 调用失败时的降级处理。

        直接使用热点话题生成简单的话题候选：
        - 使用查询计划的车道标签作为角度
        - 推断话题类型（基于证据来源）
        - 设置默认的钩子和情感定位

        Args:
            error: 发生的异常
            input_data: 原始输入数据

        Returns:
            AgentResult: 基于热点话题生成的简化话题列表
        """
        hot_topics = input_data.get("hot_topics") or {}
        query_plan = self._resolve_query_plan(input_data)
        # 获取车道标签作为默认角度
        lane_label = ((query_plan.get("lane") or {}).get("label")) or "通用洞察"
        digest = input_data.get("reference_digest") or {}
        # 获取首选来源
        preferred_sources = digest.get("preferred_source_names") if isinstance(digest, dict) else []
        selected_evidence = input_data.get("selected_evidence") or []
        # 获取目标读者
        target_reader = (
            (input_data.get("account_context") or {}).get("audience")
            or (input_data.get("profile") or {}).get("target_audience")
            or "this account's core readers"
        )

        topics: list[dict[str, Any]] = []
        # 遍历热点话题
        for item in hot_topics.get("hot_topics", []) if isinstance(hot_topics.get("hot_topics"), list) else []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            # 生成证据引用
            evidence_refs = [
                str(item.get("title") or "").strip()
                for item in selected_evidence[:2]
                if isinstance(item, dict) and str(item.get("title") or "").strip()
            ]
            # 推断话题类型
            topic_kind = "general_analysis"
            if any(
                isinstance(item, dict) and str(item.get("source_type") or "").startswith("github")
                for item in selected_evidence
            ):
                topic_kind = "github_project_review"
            elif any(
                isinstance(item, dict) and str(item.get("source_type") or "").startswith("scholar")
                for item in selected_evidence
            ):
                topic_kind = "paper_digest"
            topics.append(
                {
                    "title": title,
                    "angle": f"Use the {lane_label} lane to turn this hot topic into an account-owned judgment.",
                    "hook": "scene + contradiction",
                    "target_emotion": "recognition",
                    "estimated_appeal": float(item.get("relevance_score") or 0.65),
                    "reasoning": f"This topic already shows relevance and can be localized for {target_reader}.",
                    "why_now": "Source scouting shows the topic is active enough to justify a timely piece.",
                    "reference_basis": ", ".join(preferred_sources[:2]) if preferred_sources else "reference digest",
                    "target_reader": str(target_reader),
                    "content_lane": lane_label,
                    "topic_kind": topic_kind,
                    "evidence_refs": evidence_refs,
                }
            )
            # 最多生成 3 个话题
            if len(topics) >= 3:
                break

        return self._success({"topics": topics})

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        """构建 LLM 用户提示词。

        整合账号快照、热点话题、参考摘要、证据等信息，
        生成完整的话题规划提示词。

        Args:
            input_data: 原始输入数据

        Returns:
            str: 完整的用户提示词
        """
        profile = input_data.get("profile") or {}
        hot_topics = input_data.get("hot_topics") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = input_data.get("reference_digest") or {}
        source_candidates = input_data.get("source_candidates") or []
        selected_evidence = input_data.get("selected_evidence") or []
        evidence_summaries = input_data.get("evidence_summaries") or {}

        # 构建账号快照
        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
            "preferred_content_lane": (ops_context.get("run_strategy") or {}).get("preferred_content_lane") or "",
        }

        # 获取热点话题列表
        hot_snapshot = hot_topics.get("hot_topics") if isinstance(hot_topics.get("hot_topics"), list) else []
        return "\n".join(
            [
                "Create topic candidates for the next article.",
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
                "SOURCE CANDIDATES",
                article_assembler_service.to_pretty_json(source_candidates[:6] if isinstance(source_candidates, list) else []),
                "",
                "HOT TOPICS",
                article_assembler_service.to_pretty_json(hot_snapshot[:8]),
                "",
                "RETURN CONTRACT",
                "- Return JSON with topics.",
                "- Provide 3-5 topics.",
                "- Each topic must include title, angle, hook, target_emotion, estimated_appeal, reasoning, why_now, reference_basis, target_reader, content_lane, topic_kind, evidence_refs.",
                "- angle should explain the account-owned perspective, not just paraphrase the hot topic title.",
                "- If the topic is grounded in a paper or repo, topic_kind and evidence_refs must reflect that evidence explicitly.",
            ]
        )

    def _resolve_query_plan(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """解析或构建查询计划。

        如果输入中包含查询计划则直接使用，
        否则调用服务构建新的查询计划。

        Args:
            input_data: 原始输入数据

        Returns:
            dict: 查询计划
        """
        query_plan = input_data.get("query_plan")
        if isinstance(query_plan, dict):
            return query_plan
        # 调用服务构建查询计划
        return query_planner_service.build_plan(
            profile=input_data.get("profile") or {},
            account_context=input_data.get("account_context") or {},
            ops_context=input_data.get("ops_context") or {},
            hot_topics=input_data.get("hot_topics") or {},
        )

    def _normalize_topics(self, data: dict[str, Any]) -> dict[str, Any]:
        """规范化话题列表。

        确保每个话题包含所有必需字段，
        设置默认值，处理可能的格式错误。

        Args:
            data: LLM 返回的原始数据

        Returns:
            dict: 规范化后的话题列表
        """
        raw_topics = data.get("topics") if isinstance(data, dict) else None
        normalized: list[dict[str, Any]] = []
        if isinstance(raw_topics, list):
            for item in raw_topics:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                normalized.append(
                    {
                        "title": title,
                        "angle": str(item.get("angle") or "").strip(),
                        "hook": str(item.get("hook") or "").strip(),
                        "target_emotion": str(item.get("target_emotion") or "").strip(),
                        "estimated_appeal": float(item.get("estimated_appeal") or 0.0),
                        "reasoning": str(item.get("reasoning") or "").strip(),
                        "why_now": str(item.get("why_now") or "").strip(),
                        "reference_basis": str(item.get("reference_basis") or "").strip(),
                        "target_reader": str(item.get("target_reader") or "").strip(),
                        "content_lane": str(item.get("content_lane") or "").strip(),
                        "topic_kind": str(item.get("topic_kind") or "general_analysis").strip() or "general_analysis",
                        "evidence_refs": [
                            str(ref).strip()
                            for ref in item.get("evidence_refs", [])
                            if str(ref).strip()
                        ] if isinstance(item.get("evidence_refs"), list) else [],
                    }
                )
        return {"topics": normalized}

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
