"""Outline planner agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service


class OutlinePlannerAgent(BaseAgent):
    """Generate a structured outline before long-form writing."""

    agent_id = "outline_planner_agent"
    name = "Outline Planner"
    description = "Plan a structured outline before section-by-section writing."

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "hot_topics": {"type": "object"},
            "topics": {"type": "object"},
            "titles": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
        },
        "required": ["profile", "topics", "titles"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "article_goal": {"type": "string"},
            "target_reader_takeaway": {"type": "string"},
            "opening_hook": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_id": {"type": "string"},
                        "id": {"type": "string"},
                        "heading": {"type": "string"},
                        "title": {"type": "string"},
                        "purpose": {"type": "string"},
                        "goal": {"type": "string"},
                        "summary": {"type": "string"},
                        "key_points": {"type": "array", "items": {"type": "string"}},
                        "tone_hint": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "ending_cta": {"type": "string"},
            "estimated_word_count": {"type": "integer"},
            "summary": {"type": "string"},
        },
    }

    default_system_prompt = """You are an experienced WeChat long-form editor.

Your job is to convert a chosen topic and title into a practical article outline.
Return strict JSON only.

Requirements:
- Respect the account positioning, audience, tone, automation plan summary, and ops context.
- Use the preferred content lane when available.
- Avoid repeating recent topics listed in ops_context.run_strategy.avoid_recent_topics.
- Keep the outline concrete and section-based.
- Write for a readable public-account article, not for an academic paper.
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
            data = self._parse_json(content)
            return self._success(self._normalize_outline(data))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse outline JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        selected_title = article_assembler_service.extract_selected_title(input_data.get("titles"))
        selected_topic = article_assembler_service.extract_selected_topic(
            input_data.get("topics"), input_data.get("titles")
        )
        lane = (
            (input_data.get("ops_context") or {})
            .get("run_strategy", {})
            .get("preferred_content_lane")
        ) or "insight"

        sections = [
            self._build_section(
                "s1",
                "Open with a relatable tension",
                "Explain why the topic matters right now",
                [
                    f"Use a hook that makes the reader feel seen around {selected_topic or selected_title}.",
                    "Set up the reader's real-world problem quickly.",
                ],
                "Warm, direct, concise",
            ),
            self._build_section(
                "s2",
                "Break down the key observation",
                "Give the main interpretation and useful framing",
                [
                    f"Use the {lane} lane as the main angle.",
                    "Translate abstract ideas into lived scenarios.",
                ],
                "Grounded and practical",
            ),
            self._build_section(
                "s3",
                "Offer concrete actions",
                "Turn the argument into clear takeaways",
                [
                    "List 2-3 practical actions or reflections.",
                    "End with a small next step the reader can actually do.",
                ],
                "Supportive and actionable",
            ),
        ]
        outline = {
            "article_goal": f"Help readers understand and act on {selected_topic or selected_title}.",
            "target_reader_takeaway": "Leave with one clearer perspective and one doable action.",
            "opening_hook": f"Start from a familiar feeling around {selected_topic or selected_title}.",
            "sections": sections,
            "ending_cta": "Invite the reader to reflect, comment, or save the article for later.",
            "estimated_word_count": 1200,
            "summary": f"Structured outline fallback for {selected_title}.",
        }
        return self._success(outline)

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        profile = input_data.get("profile") or {}
        topics = input_data.get("topics") or {}
        titles = input_data.get("titles") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        hot_topics = input_data.get("hot_topics") or {}

        selected_title = article_assembler_service.extract_selected_title(titles)
        selected_topic = article_assembler_service.extract_selected_topic(topics, titles)
        title_candidates = article_assembler_service.extract_title_candidates(titles)
        preferred_lane = (ops_context.get("run_strategy") or {}).get("preferred_content_lane")
        avoid_topics = (ops_context.get("run_strategy") or {}).get("avoid_recent_topics") or []
        preferred_source_ids = (ops_context.get("run_strategy") or {}).get("preferred_reference_source_ids") or []
        reference_summaries = account_context.get("reference_sources") or []
        hot_items = hot_topics.get("hot_topics") if isinstance(hot_topics, dict) else []

        return "\n".join(
            [
                "Create a practical outline for a WeChat article.",
                "",
                "ACCOUNT",
                f"- name: {account_context.get('account_name') or 'unknown'}",
                f"- positioning: {account_context.get('positioning') or profile.get('positioning_raw') or ''}",
                f"- audience: {account_context.get('audience') or profile.get('target_audience') or ''}",
                f"- tone: {account_context.get('tone_style') or profile.get('tone') or ''}",
                f"- content strategy: {account_context.get('content_strategy') or ''}",
                f"- automation plan: {account_context.get('automation_plan_summary') or ''}",
                "",
                "OPS CONTEXT",
                f"- preferred_content_lane: {preferred_lane or ''}",
                f"- effective_mode: {(ops_context.get('run_strategy') or {}).get('effective_mode') or ''}",
                f"- avoid_recent_topics: {avoid_topics}",
                f"- preferred_reference_source_ids: {preferred_source_ids}",
                "",
                "TOPIC AND TITLE",
                f"- selected_topic: {selected_topic}",
                f"- selected_title: {selected_title}",
                f"- title_candidates: {title_candidates}",
                "",
                "REFERENCE SOURCE SUMMARY",
                f"- sources: {reference_summaries}",
                "",
                "HOT SIGNALS",
                f"- hot_topics: {hot_items[:3] if isinstance(hot_items, list) else []}",
                "",
                "Return JSON with article_goal, target_reader_takeaway, opening_hook, sections, ending_cta, estimated_word_count, summary.",
            ]
        )

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

    def _normalize_outline(self, data: dict[str, Any]) -> dict[str, Any]:
        sections = data.get("sections")
        normalized_sections: list[dict[str, Any]] = []
        if isinstance(sections, list):
            for index, item in enumerate(sections):
                if not isinstance(item, dict):
                    continue
                section_id = item.get("section_id") or item.get("id") or f"s{index + 1}"
                heading = str(item.get("heading") or item.get("title") or f"Section {index + 1}").strip()
                purpose = str(item.get("purpose") or item.get("goal") or "").strip()
                normalized_sections.append(
                    self._build_section(
                        str(section_id),
                        heading,
                        purpose or heading,
                        item.get("key_points") if isinstance(item.get("key_points"), list) else [],
                        str(item.get("tone_hint") or "").strip() or "Warm and readable",
                        summary=str(item.get("summary") or purpose).strip() or None,
                        evidence_refs=item.get("evidence_refs") if isinstance(item.get("evidence_refs"), list) else [],
                    )
                )

        return {
            "article_goal": str(data.get("article_goal") or "").strip(),
            "target_reader_takeaway": str(data.get("target_reader_takeaway") or "").strip(),
            "opening_hook": str(data.get("opening_hook") or "").strip(),
            "sections": normalized_sections,
            "ending_cta": str(data.get("ending_cta") or "").strip(),
            "estimated_word_count": int(data.get("estimated_word_count") or 1200),
            "summary": str(data.get("summary") or data.get("article_goal") or "").strip(),
        }

    def _build_section(
        self,
        section_id: str,
        heading: str,
        purpose: str,
        key_points: list[Any],
        tone_hint: str,
        *,
        summary: str | None = None,
        evidence_refs: list[Any] | None = None,
    ) -> dict[str, Any]:
        normalized_key_points = [str(item).strip() for item in key_points if str(item).strip()]
        normalized_evidence = [str(item).strip() for item in (evidence_refs or []) if str(item).strip()]
        return {
            "section_id": section_id,
            "id": section_id,
            "heading": heading,
            "title": heading,
            "purpose": purpose,
            "goal": purpose,
            "summary": summary or purpose,
            "key_points": normalized_key_points,
            "tone_hint": tone_hint,
            "evidence_refs": normalized_evidence,
        }
