"""Title generator agent for source-backed topic candidates."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service


class TitleGeneratorAgent(BaseAgent):
    """Generate title candidates for the strongest topic package."""

    agent_id = "title_generator_agent"
    name = "Title Generator"
    description = "Generate title candidates grounded in strategy and reference cues."

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
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

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
            return self._success(self._normalize_titles(self._parse_json(content), input_data))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse title JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
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
        profile = input_data.get("profile") or {}
        topics = input_data.get("topics") or {}
        account_context = input_data.get("account_context") or {}
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

        sorted_topics = self._sorted_topics(topics)
        topic_package = sorted_topics[:3]
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
