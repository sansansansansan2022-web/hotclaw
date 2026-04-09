"""Section writer agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import BaseAgent, AgentResult
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service


class SectionWriterAgent(BaseAgent):
    """Write article sections one by one from an outline plan."""

    agent_id = "section_writer_agent"
    name = "Section Writer"
    description = "Draft article sections from the structured outline."

    input_schema = {
        "type": "object",
        "properties": {
            "outline_plan": {"type": "object"},
            "profile": {"type": "object"},
            "topics": {"type": "object"},
            "titles": {"type": "object"},
            "hot_topics": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
        },
        "required": ["outline_plan", "titles"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "section_drafts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_id": {"type": "string"},
                        "id": {"type": "string"},
                        "heading": {"type": "string"},
                        "summary": {"type": "string"},
                        "content_markdown": {"type": "string"},
                        "word_count": {"type": "integer"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }

    default_system_prompt = """You are a careful long-form article writer for WeChat.

Write section-level drafts from the provided outline.
Return strict JSON only.

Requirements:
- Respect account tone, audience, automation plan summary, and ops context.
- Use the preferred content lane if one is given.
- Avoid the recent topics listed in ops_context.
- Keep sections scannable and mobile-friendly.
- Each section should have a clear purpose and a concrete takeaway.
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
            return self._success(self._normalize_section_drafts(data))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse section JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        outline = input_data.get("outline_plan") or {}
        title = article_assembler_service.extract_selected_title(input_data.get("titles"))
        topic = article_assembler_service.extract_selected_topic(
            input_data.get("topics"), input_data.get("titles")
        )
        section_drafts: list[dict[str, Any]] = []

        for index, section in enumerate(outline.get("sections", [])):
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("section_id") or section.get("id") or f"s{index + 1}")
            heading = str(section.get("heading") or section.get("title") or f"Section {index + 1}").strip()
            summary = str(section.get("summary") or section.get("purpose") or "").strip()
            key_points = section.get("key_points") if isinstance(section.get("key_points"), list) else []

            paragraphs = [
                f"This section supports the article '{title}' by focusing on {heading.lower()}.",
            ]
            if topic:
                paragraphs.append(f"Keep the discussion anchored in {topic}.")
            for point in key_points[:3]:
                text = str(point).strip()
                if text:
                    paragraphs.append(f"- {text}")

            content_markdown = "\n\n".join(paragraphs)
            section_drafts.append(
                {
                    "section_id": section_id,
                    "id": section_id,
                    "heading": heading,
                    "summary": summary or heading,
                    "content_markdown": content_markdown,
                    "word_count": article_assembler_service.count_words(content_markdown),
                    "evidence_refs": section.get("evidence_refs") or [],
                }
            )

        return self._success({"section_drafts": section_drafts})

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        outline = input_data.get("outline_plan") or {}
        account_context = input_data.get("account_context") or {}
        profile = input_data.get("profile") or {}
        ops_context = input_data.get("ops_context") or {}
        titles = input_data.get("titles") or {}
        topics = input_data.get("topics") or {}

        selected_title = article_assembler_service.extract_selected_title(titles)
        selected_topic = article_assembler_service.extract_selected_topic(topics, titles)
        preferred_lane = (ops_context.get("run_strategy") or {}).get("preferred_content_lane")

        return "\n".join(
            [
                "Write section-level article drafts from this outline.",
                "",
                "ACCOUNT",
                f"- name: {account_context.get('account_name') or 'unknown'}",
                f"- positioning: {account_context.get('positioning') or profile.get('positioning_raw') or ''}",
                f"- audience: {account_context.get('audience') or profile.get('target_audience') or ''}",
                f"- tone: {account_context.get('tone_style') or profile.get('tone') or ''}",
                f"- content strategy: {account_context.get('content_strategy') or ''}",
                "",
                "OPS CONTEXT",
                f"- effective_mode: {(ops_context.get('run_strategy') or {}).get('effective_mode') or ''}",
                f"- preferred_content_lane: {preferred_lane or ''}",
                f"- avoid_recent_topics: {(ops_context.get('run_strategy') or {}).get('avoid_recent_topics') or []}",
                "",
                "ARTICLE",
                f"- selected_topic: {selected_topic}",
                f"- selected_title: {selected_title}",
                f"- outline_plan: {outline}",
                "",
                "Return JSON with section_drafts. Each section_draft must include section_id, heading, summary, content_markdown, word_count, evidence_refs.",
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

    def _normalize_section_drafts(self, data: dict[str, Any]) -> dict[str, Any]:
        items = data.get("section_drafts") if isinstance(data, dict) else None
        if not isinstance(items, list):
            items = []

        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id") or item.get("id") or f"s{index + 1}")
            heading = str(item.get("heading") or item.get("title") or f"Section {index + 1}").strip()
            content_markdown = str(item.get("content_markdown") or item.get("content") or "").strip()
            normalized.append(
                {
                    "section_id": section_id,
                    "id": section_id,
                    "heading": heading,
                    "summary": str(item.get("summary") or heading).strip(),
                    "content_markdown": content_markdown,
                    "word_count": int(item.get("word_count") or article_assembler_service.count_words(content_markdown)),
                    "evidence_refs": [
                        str(ref).strip()
                        for ref in (item.get("evidence_refs") or [])
                        if str(ref).strip()
                    ],
                }
            )
        return {"section_drafts": normalized}
