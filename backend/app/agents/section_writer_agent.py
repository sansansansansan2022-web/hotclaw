"""Section writer agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service


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
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
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
- The selected_topic and selected_title are locked. Do not widen or swap them for a neighboring theme.
- Respect account tone, audience, lane, reference digest, and source-scout context.
- Each section must fulfill its own purpose, not just restate the article theme in new words.
- Keep sections scannable and mobile-friendly, but do not sound like a checklist.
- Reduce AI tone: no generic comfort-talk, no padded summaries, no rigid 'first/second/finally' scaffolding.
- Make each section carry concrete movement through observation, contrast, scene, example, or action.
- When evidence_refs are present, let them shape emphasis and texture, but do not fabricate facts.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)
        selected_title = article_assembler_service.extract_selected_title(input_data.get("titles"))
        selected_topic = article_assembler_service.extract_selected_topic(
            input_data.get("topics"), input_data.get("titles")
        )

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
            normalized = self._normalize_section_drafts(self._parse_json(content))
            if not self._section_drafts_match_topic(normalized, selected_topic, selected_title):
                fallback_result = await self.fallback(RuntimeError("section topic drift detected"), input_data)
                if fallback_result and fallback_result.is_success:
                    return fallback_result
            return self._success(normalized)
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
            transition_hint = str(
                section.get("section_transition_hint") or section.get("transition_hint") or ""
            ).strip()

            paragraphs = [
                f"In '{title}', this section turns toward {heading.lower()} with a clear job to do.",
            ]
            if topic:
                paragraphs.append(
                    f"Keep the discussion anchored in {topic}, but move it forward instead of reintroducing the topic from zero."
                )
            if summary:
                paragraphs.append(summary)
            for point in key_points[:3]:
                text = str(point).strip()
                if text:
                    paragraphs.append(text)
            if transition_hint:
                paragraphs.append(transition_hint)

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
        source_candidates = input_data.get("source_candidates") or []

        selected_title = article_assembler_service.extract_selected_title(titles)
        selected_topic = article_assembler_service.extract_selected_topic(topics, titles)
        outline_summary = article_assembler_service.summarize_outline_plan(outline)
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = self._resolve_reference_digest(input_data, query_plan)
        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
            "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
        }
        ops_snapshot = {
            "effective_mode": (ops_context.get("run_strategy") or {}).get("effective_mode") or "",
            "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
            "avoid_recent_topics": (ops_context.get("run_strategy") or {}).get("avoid_recent_topics") or [],
            "preferred_reference_source_ids": (ops_context.get("run_strategy") or {}).get("preferred_reference_source_ids") or [],
        }
        article_blueprint = {
            "selected_topic": selected_topic,
            "selected_title": selected_title,
            "article_goal": outline_summary.get("article_goal"),
            "why_this_topic": outline_summary.get("why_this_topic"),
            "strategic_angle": outline_summary.get("strategic_angle"),
            "reference_basis": outline_summary.get("reference_basis"),
            "target_reader": outline_summary.get("target_reader"),
            "content_lane": outline_summary.get("content_lane"),
            "target_reader_takeaway": outline_summary.get("target_reader_takeaway"),
            "opening_hook": outline_summary.get("opening_hook"),
            "ending_cta": outline_summary.get("ending_cta"),
            "emotional_arc": outline_summary.get("emotional_arc"),
            "sections": self._build_section_briefs(outline_summary),
        }

        return "\n".join(
            [
                "Write section-level article drafts from this outline.",
                "The result should read like a writer drafting in sequence, not like a model filling a worksheet.",
                "",
                "WRITING RULES",
                f"- Stay locked to this exact topic/title pair: {selected_topic} / {selected_title}. Do not widen it into the account's general domain.",
                "- Follow each section's purpose and key_points closely. If a key point is weak, deepen it with observation or contrast instead of drifting away.",
                "- The first section should inherit the energy of opening_hook. The last section should set up or echo ending_cta without sounding like a conclusion template.",
                "- Use the preferred content lane and preferred reference-source cues to shape framing, cadence, and emphasis.",
                "- Use source-candidate texture to make the writing feel grounded, but do not copy or fabricate facts.",
                "- Do not repeat what the previous section already established. Each new section must add something meaningfully new.",
                "- Avoid these anti-patterns: empty background explanation, hollow motivational sentences, over-symmetry, 'first/second/finally', 'in conclusion/to sum up', and summary after summary.",
                "- Every section should contain concrete movement: a scene, a sharp observation, a contrast, a mini-example, or a usable action.",
                "",
                "ACCOUNT SNAPSHOT",
                article_assembler_service.to_pretty_json(account_snapshot),
                "",
                "OPS SNAPSHOT",
                article_assembler_service.to_pretty_json(ops_snapshot),
                "",
                "QUERY PLAN",
                article_assembler_service.to_pretty_json(query_plan),
                "",
                "REFERENCE STYLE BRIEF",
                article_assembler_service.to_pretty_json(reference_digest),
                "",
                "SOURCE CANDIDATES",
                article_assembler_service.to_pretty_json(source_candidates[:5] if isinstance(source_candidates, list) else []),
                "",
                "ARTICLE BLUEPRINT",
                article_assembler_service.to_pretty_json(article_blueprint),
                "",
                "RETURN CONTRACT",
                "- Return JSON with section_drafts.",
                "- Each section_draft must include section_id, heading, summary, content_markdown, word_count, evidence_refs.",
                "- content_markdown should be 2-5 short paragraphs or purposeful bullets only when the section naturally calls for bullets.",
                "- summary should say what the section now accomplishes, not repeat the heading verbatim.",
                "",
                "Return JSON with section_drafts. Each section_draft must include section_id, heading, summary, content_markdown, word_count, evidence_refs.",
            ]
        )

    def _resolve_query_plan(self, input_data: dict[str, Any]) -> dict[str, Any]:
        query_plan = input_data.get("query_plan")
        if isinstance(query_plan, dict):
            return query_plan
        return query_planner_service.build_plan(
            profile=input_data.get("profile") or {},
            account_context=input_data.get("account_context") or {},
            ops_context=input_data.get("ops_context") or {},
            selected_topic=article_assembler_service.extract_selected_topic(
                input_data.get("topics"), input_data.get("titles")
            ),
            selected_title=article_assembler_service.extract_selected_title(input_data.get("titles")),
            hot_topics=input_data.get("hot_topics") or {},
        )

    def _resolve_reference_digest(
        self,
        input_data: dict[str, Any],
        query_plan: dict[str, Any],
    ) -> dict[str, Any]:
        reference_digest = input_data.get("reference_digest")
        if isinstance(reference_digest, dict):
            return reference_digest
        return reference_digest_service.build_reference_digest(
            account_context=input_data.get("account_context") or {},
            ops_context=input_data.get("ops_context") or {},
            query_plan=query_plan,
            source_candidates=input_data.get("source_candidates") or [],
            selected_topic=article_assembler_service.extract_selected_topic(
                input_data.get("topics"), input_data.get("titles")
            ),
            selected_title=article_assembler_service.extract_selected_title(input_data.get("titles")),
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

    def _section_drafts_match_topic(
        self,
        section_drafts: dict[str, Any],
        selected_topic: str,
        selected_title: str,
    ) -> bool:
        drafts = section_drafts.get("section_drafts") if isinstance(section_drafts, dict) else []
        if not isinstance(drafts, list):
            return False

        combined_text = " ".join(
            " ".join(
                [
                    str(item.get("heading") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("content_markdown") or ""),
                ]
            )
            for item in drafts
            if isinstance(item, dict)
        )
        return article_assembler_service.text_matches_topic(
            combined_text,
            selected_topic=selected_topic,
            selected_title=selected_title,
        )

    def _build_section_briefs(self, outline_summary: dict[str, Any]) -> list[dict[str, Any]]:
        sections = outline_summary.get("sections") if isinstance(outline_summary, dict) else []
        if not isinstance(sections, list):
            return []

        total_sections = len(sections)
        estimated_word_count = int(outline_summary.get("estimated_word_count") or 1200)
        target_words = self._estimate_target_words(total_sections, estimated_word_count)

        briefs: list[dict[str, Any]] = []
        for index, section in enumerate(sections):
            if not isinstance(section, dict):
                continue
            article_position = "middle"
            if index == 0:
                article_position = "opening"
            elif index == total_sections - 1:
                article_position = "closing"
            briefs.append(
                {
                    "section_id": section.get("section_id") or f"s{index + 1}",
                    "article_position": article_position,
                    "heading": section.get("heading"),
                    "purpose": section.get("purpose"),
                    "summary": section.get("summary"),
                    "key_points": section.get("key_points") or [],
                    "tone_hint": section.get("tone_hint"),
                    "section_transition_hint": section.get("section_transition_hint"),
                    "evidence_refs": section.get("evidence_refs") or [],
                    "target_words": target_words[index] if index < len(target_words) else None,
                }
            )
        return briefs

    def _estimate_target_words(self, section_count: int, estimated_word_count: int) -> list[int]:
        if section_count <= 0:
            return []
        if section_count == 1:
            return [estimated_word_count]

        weights = [1.0 for _ in range(section_count)]
        weights[0] = 0.95
        weights[-1] = 0.9
        for index in range(1, section_count - 1):
            weights[index] = 1.1

        weight_sum = sum(weights) or float(section_count)
        return [max(180, int(estimated_word_count * weight / weight_sum)) for weight in weights]
