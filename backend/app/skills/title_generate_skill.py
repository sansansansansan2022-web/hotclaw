"""Title generation skill and shared prompt/normalization helpers."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.core.config import settings
from app.platforms import collect_platform_prompt_hints, resolve_content_platform
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service
from app.skills.base import BaseSkill, SkillResult


class TitleGenerateMixin:
    """Shared title-generation behavior used by both the agent shell and the skill."""

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

    default_system_prompt = """You are a multi-platform title strategist for WeChat and Xiaohongshu.

Choose the strongest topic candidate and generate 4-6 titles that feel click-worthy without losing credibility.
Return strict JSON only.

Rules:
- Titles must reflect the chosen topic package, account voice, and source-backed angle.
- Avoid empty shock-value or titles that could belong to any account.
- Show style diversity, but keep the title promises compatible with the outline the team will later write.
- Do not invent specific paper names or repo names that are absent from the evidence list.
- If content_platform is xiaohongshu, write note-style titles: concrete result, first-person/scene if useful, searchable keywords, cover-friendly length, and no public-account essay phrasing.
- If content_platform is wechat, keep long-form public-account title logic.
"""

    def build_messages(self, input_data: dict[str, Any], system_prompt: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self._build_user_prompt(input_data)},
        ]

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        profile = input_data.get("profile") or {}
        topics = input_data.get("topics") or {}
        account_context = input_data.get("account_context") or {}
        content_platform = resolve_content_platform(account_context, profile)
        platform_hints = collect_platform_prompt_hints(account_context, "recommendation")
        ops_context = input_data.get("ops_context") or {}
        query_plan = input_data.get("query_plan")
        if not isinstance(query_plan, dict):
            query_plan = query_planner_service.build_plan(
                profile=profile,
                account_context=account_context,
                ops_context=ops_context,
            )
        reference_digest = input_data.get("reference_digest") or {}
        selected_evidence = input_data.get("selected_evidence") or []
        evidence_summaries = input_data.get("evidence_summaries") or {}
        topic_package = self._sorted_topics(topics)[:3]

        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
            "content_platform": content_platform,
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
                "PLATFORM CAPABILITY HINTS",
                article_assembler_service.to_pretty_json(platform_hints),
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
                "- For xiaohongshu, include at least two cover-friendly titles that are short enough for a square cover and one searchable title with concrete keywords.",
            ]
        )

    def _sorted_topics(self, topics: dict[str, Any]) -> list[dict[str, Any]]:
        items = topics.get("topics") if isinstance(topics.get("topics"), list) else []
        normalized = [item for item in items if isinstance(item, dict)]
        normalized.sort(key=lambda item: float(item.get("estimated_appeal") or 0.0), reverse=True)
        return normalized

    def _pick_topic(self, topics: dict[str, Any]) -> str:
        sorted_topics = self._sorted_topics(topics)
        if sorted_topics:
            return str(sorted_topics[0].get("title") or "").strip()
        return ""

    def _normalize_titles(self, data: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        selected_topic = str(data.get("selected_topic") or self._pick_topic(input_data.get("topics") or {})).strip()
        raw_titles = data.get("titles") if isinstance(data, dict) else None
        normalized_titles: list[dict[str, Any]] = []
        if isinstance(raw_titles, list):
            for item in raw_titles:
                if not isinstance(item, dict):
                    continue
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
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)


class TitleGenerateSkill(BaseSkill, TitleGenerateMixin):
    """Reusable capability for generating title candidates from topic packages."""

    skill_id = "title_generate_skill"
    name = "Title Generate Skill"
    description = "Generate title candidates grounded in strategy and reference cues."

    input_schema = TitleGenerateMixin.input_schema
    output_schema = TitleGenerateMixin.output_schema

    async def execute(self, input_data: dict) -> dict:
        system_prompt = str(input_data.get("system_prompt") or self.default_system_prompt)
        try:
            response = await litellm.acompletion(
                messages=self.build_messages(input_data, system_prompt),
                timeout=settings.llm_timeout,
            )
            content = response.choices[0].message.content
            data = self._normalize_titles(self._parse_json(content), input_data)
            return SkillResult.success(self.skill_id, data).to_dict()
        except json.JSONDecodeError as exc:
            return SkillResult.failure(
                self.skill_id,
                "JSON_PARSE_ERROR",
                f"Failed to parse title JSON: {exc}",
            ).to_dict()
        except Exception as exc:
            return SkillResult.failure(self.skill_id, "LLM_ERROR", str(exc)).to_dict()


title_generate_skill = TitleGenerateSkill()
