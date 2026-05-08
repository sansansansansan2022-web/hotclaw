"""Topic selection agent: select topics AND generate titles in one LLM call."""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_gateway import llm_gateway


class TopicSelectionAgent(BaseAgent):
    """One-pass topic selection and title generation.

    Replaces topic_planner_agent + title_generator_agent with a single LLM call.
    Output populates both `topics` and `titles` workspace keys.
    """

    agent_id = "topic_selection_agent"
    name = "选题与标题"
    description = "一次 LLM 调用完成选题策划和标题生成，输出 topics + titles。"

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "hot_topics": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
        },
        "required": ["profile", "hot_topics"],
    }

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
                    },
                },
            },
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

    default_system_prompt = """\
你是资深公众号策划编辑，擅长结合账号定位和热点趋势策划选题、生成爆款标题。

## 两步任务（请在一次回答中完成）
1. **选题策划**：综合账号画像和热点，策划 3-5 个候选选题，按吸引力降序排列
2. **标题生成**：为吸引力最高的选题生成 4-6 个风格各异的候选标题，并评分

## 输出规范
必须返回如下 JSON，不得输出其他内容：
{
  "topics": [
    {
      "title": string,            // 选题方向标题
      "angle": string,            // 切入角度
      "hook": string,             // 钩子类型（如"恐惧+自检"、"案例+希望"）
      "target_emotion": string,   // 目标触发情绪
      "estimated_appeal": float,  // 0.0~1.0
      "reasoning": string         // 选题理由
    }
  ],
  "selected_topic": string,       // 选中的选题标题（即 topics 中 estimated_appeal 最高的）
  "titles": [
    {
      "text": string,             // 标题文本，15~30 字
      "style": string,            // 悬念型/数字型/故事型/反问型/警告型/实用型
      "score": float,             // 1.0~10.0
      "reasoning": string         // 评分理由
    }
  ]
}

## 约束
- topics 按 estimated_appeal 降序排列，titles 按 score 降序排列
- 标题必须符合账号调性，不要过度标题党，长度 15-30 字
- 不同标题风格需覆盖至少 3 种类型
- selected_topic 必须与 topics[0].title 完全一致
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

        try:
            response = await llm_gateway.complete(
                agent_id=self.agent_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format="json",
            )
            return self._success(self._normalize(response.parsed or {}))
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        profile = input_data.get("profile") or {}
        hot_topics = input_data.get("hot_topics") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}

        domain = profile.get("domain") or account_context.get("category") or "未知"
        subdomain = profile.get("subdomain") or ""
        tone = profile.get("tone") or account_context.get("tone_style") or "中性"
        audience = profile.get("target_audience") or account_context.get("audience") or {}
        keywords = profile.get("keywords") or []
        positioning = profile.get("positioning_raw") or account_context.get("positioning") or ""
        preferred_lane = (ops_context.get("run_strategy") or {}).get("preferred_content_lane") or ""
        avoid_topics = (ops_context.get("run_strategy") or {}).get("avoid_recent_topics") or []

        topics_list = hot_topics.get("hot_topics") if isinstance(hot_topics, dict) else []

        parts = [
            "请完成选题策划和标题生成两步任务，一次性输出完整 JSON。",
            "",
            "## 账号信息",
            f"- 主领域: {domain}" + (f"（{subdomain}）" if subdomain else ""),
            f"- 内容调性: {tone}",
            f"- 账号定位: {positioning}" if positioning else "",
            f"- 目标读者: {audience.get('occupation', '通用') if isinstance(audience, dict) else str(audience)}",
            f"- 优选内容赛道: {preferred_lane}" if preferred_lane else "",
        ]
        if keywords:
            parts.append(f"- 关键词: {', '.join(str(k) for k in keywords[:8])}")
        if avoid_topics:
            parts.append(f"- 近期应回避的话题: {', '.join(str(t) for t in avoid_topics[:5])}")

        if isinstance(topics_list, list) and topics_list:
            parts += ["", "## 当前热点（按热度排序）"]
            for i, topic in enumerate(topics_list[:6], 1):
                title = topic.get("title") or ""
                source = topic.get("source") or ""
                heat = topic.get("heat_score") or 0
                relevance = topic.get("relevance_score") or 0
                parts.append(f"{i}. {title}（来源:{source} 热度:{heat} 相关度:{relevance}）")

        parts += ["", "请输出完整选题策划 + 标题方案的 JSON。"]
        return "\n".join(p for p in parts if p is not None)

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        raw_topics = data.get("topics")
        topics: list[dict[str, Any]] = []
        if isinstance(raw_topics, list):
            for item in raw_topics:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                appeal = item.get("estimated_appeal")
                try:
                    appeal = max(0.0, min(1.0, float(appeal))) if appeal is not None else 0.5
                except (TypeError, ValueError):
                    appeal = 0.5
                topics.append(
                    {
                        "title": title,
                        "angle": str(item.get("angle") or "").strip(),
                        "hook": str(item.get("hook") or "").strip(),
                        "target_emotion": str(item.get("target_emotion") or "").strip(),
                        "estimated_appeal": appeal,
                        "reasoning": str(item.get("reasoning") or "").strip(),
                    }
                )
        topics.sort(key=lambda t: t["estimated_appeal"], reverse=True)

        selected_topic = str(data.get("selected_topic") or "").strip()
        if not selected_topic and topics:
            selected_topic = topics[0]["title"]

        raw_titles = data.get("titles")
        titles: list[dict[str, Any]] = []
        if isinstance(raw_titles, list):
            for item in raw_titles:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                score = item.get("score")
                try:
                    score = max(0.0, min(10.0, float(score))) if score is not None else 5.0
                except (TypeError, ValueError):
                    score = 5.0
                titles.append(
                    {
                        "text": text,
                        "style": str(item.get("style") or "default").strip(),
                        "score": score,
                        "reasoning": str(item.get("reasoning") or "").strip(),
                    }
                )
        titles.sort(key=lambda t: t["score"], reverse=True)

        return {
            "topics": topics,
            "selected_topic": selected_topic,
            "titles": titles,
        }

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        hot_topics = input_data.get("hot_topics") or {}
        topics_list = hot_topics.get("hot_topics") if isinstance(hot_topics, dict) else []
        fallback_topics = [
            {
                "title": t.get("title") or "",
                "angle": "直接引用热点",
                "hook": "热点",
                "target_emotion": "好奇",
                "estimated_appeal": 0.5,
                "reasoning": "降级策略：直接使用热点标题",
            }
            for t in (topics_list[:3] if isinstance(topics_list, list) else [])
            if t.get("title")
        ]
        if not fallback_topics:
            fallback_topics = [
                {
                    "title": "今日话题",
                    "angle": "通用",
                    "hook": "热点",
                    "target_emotion": "好奇",
                    "estimated_appeal": 0.5,
                    "reasoning": "降级",
                }
            ]
        selected = fallback_topics[0]["title"]
        return self._success(
            {
                "topics": fallback_topics,
                "selected_topic": selected,
                "titles": [
                    {"text": selected, "style": "default", "score": 5.0, "reasoning": "降级：直接使用选题标题"}
                ],
            }
        )
