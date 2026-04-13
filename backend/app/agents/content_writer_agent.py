"""Content writer agent: generates full article content."""

# ============================================================================
# 内容写作 Agent (Content Writer Agent)
# ============================================================================
# 职责说明：
# - 基于话题候选和证据生成完整的文章内容
# - 生成 Markdown 格式的文章正文
# - 设计文章结构和章节安排
# - 生成内容标签
# - 严格基于证据内容，禁止虚构引用
#
# 协作关系：
# - 输入：话题 (TopicPlannerAgent)、标题 (TitleGeneratorAgent)、证据
# - 输出：完整的文章内容（Markdown 格式）
# - 为 AuditAgent 提供待审核内容
# ============================================================================

from __future__ import annotations

import json

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings


class ContentWriterAgent(BaseAgent):
    """内容写作 Agent - 基于话题和证据生成完整文章。

    核心职责：
    1. 整合话题、标题、证据等信息
    2. 生成符合账号风格的完整文章
    3. 设计清晰的文章结构（章节、段落）
    4. 生成适当的内容标签
    5. 严格基于证据，禁止虚构论文、项目或引用

    特点：
    - 专注于文章内容生成，不涉及标题创作
    - 支持多种话题类型的结构模板
    - 字数控制在 1500-3000 中文汉字
    - 移动端可读性优先
    """

    # Agent 唯一标识符
    agent_id = "content_writer_agent"
    name = "Content Writer Agent"
    description = "Generate a complete article from topics, titles, and grounded evidence."

    # 输入数据结构定义
    # profile: 账号画像
    # topics: 话题候选列表（必需）
    # titles: 标题候选列表（必需）
    # hot_topics: 热点话题（必需）
    # account_context: 账号上下文
    # selected_evidence: 选中的证据
    # evidence_summaries: 证据摘要
    # citation_guardrails: 引用规范
    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "topics": {"type": "object"},
            "titles": {"type": "object"},
            "hot_topics": {"type": "object"},
            "account_context": {"type": "object"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["profile", "topics", "titles", "hot_topics"],
    }

    # 输出数据结构定义
    # content_markdown: Markdown 格式的文章内容
    # word_count: 字数统计
    # structure: 文章结构（包含各章节标题和摘要）
    # tags: 内容标签列表
    output_schema = {
        "type": "object",
        "properties": {
            "content_markdown": {"type": "string"},
            "word_count": {"type": "integer"},
            "structure": {
                "type": "object",
                "properties": {
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "heading": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                        },
                    }
                },
            },
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }

    # 该 Agent 不使用任何 Skill
    supported_skills = []

    # 默认系统提示词
    default_system_prompt = """You are a professional Chinese long-form public-account writer.

Generate a complete article as strict JSON.

Required output fields:
- content_markdown
- word_count
- structure { sections: [{ heading, summary }] }
- tags

Rules:
- Match the account tone and audience.
- Use only grounded paper titles and repository names that exist in the provided evidence.
- Do not invent studies, benchmarks, repos, or citation claims.
- Keep paragraphs readable on mobile.
- Total length should usually stay between 1500 and 3000 Chinese characters.
- If the selected topic is paper_digest or research_trend, the article must include:
  background, problem, core method, why it matters, limitations.
- If the selected topic is github_project_review or tools_roundup, the article must include:
  project定位, who it is for, modules worth studying, risks and limits.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """执行内容写作。

        主要步骤：
        1. 提取并准备各类输入数据
        2. 构建完整的写作提示词
        3. 调用 LLM 生成文章
        4. 解析并返回文章内容

        Args:
            input_data: 包含话题、标题、证据等的输入数据
            context: 执行上下文

        Returns:
            AgentResult: 包含文章内容、字数、结构、标签
        """
        profile = input_data.get("profile", {})
        topics = input_data.get("topics", {})
        titles_data = input_data.get("titles", {})
        hot_topics = input_data.get("hot_topics", {})
        selected_evidence = input_data.get("selected_evidence") or []
        evidence_summaries = input_data.get("evidence_summaries") or {}
        citation_guardrails = input_data.get("citation_guardrails") or {}
        system_prompt = context.get("system_prompt") or self.default_system_prompt

        # 构建用户提示词
        user_prompt = self._build_user_prompt(
            profile=profile,
            topics=topics,
            titles_data=titles_data,
            hot_topics=hot_topics,
            selected_evidence=selected_evidence,
            evidence_summaries=evidence_summaries,
            citation_guardrails=citation_guardrails,
        )

        try:
            # 调用 LLM 生成文章
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
            data = self._parse_json(content)
            return self._success(data)

        except json.JSONDecodeError as exc:
            return self._failure(code="JSON_PARSE_ERROR", message=f"Failed to parse content JSON: {exc}")
        except Exception as exc:
            return self._failure(code="LLM_ERROR", message=str(exc))

    def _build_user_prompt(
        self,
        *,
        profile: dict,
        topics: dict,
        titles_data: dict,
        hot_topics: dict,
        selected_evidence: list[dict],
        evidence_summaries: dict[str, str],
        citation_guardrails: dict[str, bool],
    ) -> str:
        """构建写作提示词。

        整合账号信息、话题、标题、证据等，
        生成完整的写作指令。

        Args:
            profile: 账号画像
            topics: 话题候选列表
            titles_data: 标题候选列表
            hot_topics: 热点话题
            selected_evidence: 选中的证据
            evidence_summaries: 证据摘要
            citation_guardrails: 引用规范

        Returns:
            str: 完整的用户提示词
        """
        # 提取账号信息
        tone = profile.get("tone", "neutral")
        domain = profile.get("domain", "unknown")
        keywords = profile.get("keywords", [])

        # 获取并排序话题（按吸引力评分）
        topic_list = topics.get("topics", []) if isinstance(topics, dict) else []
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []
        hot_list = hot_topics.get("hot_topics", []) if isinstance(hot_topics, dict) else []
        sorted_topics = sorted(topic_list, key=lambda item: item.get("estimated_appeal", 0), reverse=True)
        # 选择评分最高的话题
        top_topic = sorted_topics[0] if sorted_topics else {}

        prompt_parts = [
            "Please write a complete article grounded in the following planning package.",
            "",
            "ACCOUNT",
            json.dumps(
                {
                    "domain": domain,
                    "tone": tone,
                    "keywords": keywords,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "SELECTED TOPIC",
            json.dumps(top_topic, ensure_ascii=False, indent=2),
            "",
            "TITLE CANDIDATES",
            json.dumps(title_list[:4], ensure_ascii=False, indent=2),
            "",
            "HOT TOPICS",
            json.dumps(hot_list[:6], ensure_ascii=False, indent=2),
            "",
            "EVIDENCE SUMMARIES",
            json.dumps(evidence_summaries, ensure_ascii=False, indent=2),
            "",
            "SELECTED EVIDENCE",
            json.dumps(selected_evidence[:10], ensure_ascii=False, indent=2),
            "",
            "CITATION GUARDRAILS",
            json.dumps(citation_guardrails, ensure_ascii=False, indent=2),
            "",
            "REQUIREMENTS",
            "- Output strict JSON only.",
            "- Use the highest-scoring title unless a lower one better matches the topic_kind and evidence.",
            "- Ground concrete repo names and paper names in SELECTED EVIDENCE only.",
            "- Keep the structure readable and evidence-aware.",
        ]
        return "\n".join(prompt_parts)

    def _parse_json(self, content: str) -> dict:
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

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """LLM 调用失败时的降级处理。

        返回一个表示生成失败的占位文章内容。

        Args:
            error: 发生的异常
            input_data: 原始输入数据

        Returns:
            AgentResult: 包含失败提示的文章
        """
        return self._success(
            {
                "content_markdown": "# Article generation failed\n\nThe content writer failed and no grounded article could be produced.",
                "word_count": 0,
                "structure": {"sections": []},
                "tags": [],
            }
        )
