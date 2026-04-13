"""Outline planner agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service


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
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
            "outline_seed": {"type": "object"},
        },
        "required": ["profile", "topics", "titles"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "article_goal": {"type": "string"},
            "why_this_topic": {"type": "string"},
            "strategic_angle": {"type": "string"},
            "reference_basis": {"type": "string"},
            "target_reader": {"type": "string"},
            "content_lane": {"type": "string"},
            "target_reader_takeaway": {"type": "string"},
            "opening_hook": {"type": "string"},
            "emotional_arc": {"type": "string"},
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
                        "section_transition_hint": {"type": "string"},
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

Plan an outline that feels like a real public-account article from this account, not a generic essay scaffold.
Return strict JSON only.

Non-negotiable requirements:
- The selected_topic and selected_title are locked. Do not swap to a neighboring topic, broader category, or a more familiar narrative.
- Use the account voice, audience, preferred content lane, source-scout context, and reference digest together.
- why_this_topic and strategic_angle must explain why this article deserves to exist for this account right now.
- The opening_hook must pull the reader in fast with tension, scene, contradiction, or a pointed question.
- Sections must have distinct jobs and a forward-moving relationship. Do not make them evenly padded talking points.
- The ending_cta must land with emotion, judgment, or a specific next move. Do not end with a bland summary.
- Absorb structure and voice tendencies from the preferred reference sources without copying their wording or facts.
- Avoid empty background exposition, mechanical three-step frameworks, and template-style transitions.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        outline_seed = input_data.get("outline_seed")
        if isinstance(outline_seed, dict) and outline_seed.get("sections"):
            return self._success(self._normalize_outline(outline_seed, input_data))

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
            normalized = self._normalize_outline(self._parse_json(content), input_data)
            if not self._outline_matches_topic(normalized, selected_topic, selected_title):
                fallback_result = await self.fallback(RuntimeError("outline topic drift detected"), input_data)
                if fallback_result and fallback_result.is_success:
                    return fallback_result
            return self._success(normalized)
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse outline JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        selected_title = article_assembler_service.extract_selected_title(input_data.get("titles"))
        selected_topic = article_assembler_service.extract_selected_topic(
            input_data.get("topics"), input_data.get("titles")
        )
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = self._resolve_reference_digest(input_data, query_plan)
        lane = ((query_plan.get("lane") or {}).get("label")) or "insight"
        target_reader = (
            (input_data.get("account_context") or {}).get("audience")
            or (input_data.get("profile") or {}).get("target_audience")
            or "the account's core readers"
        )
        reference_names = reference_digest.get("preferred_source_names") or ["preferred references"]
        useful_points = reference_digest.get("useful_points") or []

        sections = [
            self._build_section(
                "s1",
                "Open inside the reader's tension",
                "Use a concrete hook to make the reader feel the issue before explaining it",
                [
                    f"Drop the reader into a recognizable moment around {selected_topic or selected_title}.",
                    "Show the cost of ignoring the issue before any abstract explanation.",
                ],
                "Warm, direct, specific",
                summary="Start from the moment the reader is already living through.",
                section_transition_hint="After the hook lands, name what is really going on beneath the surface.",
                evidence_refs=reference_names[:1],
            ),
            self._build_section(
                "s2",
                "Name the pattern behind the problem",
                "Translate the surface topic into the core pattern this account wants readers to notice",
                [
                    f"Use the {lane} lane as the main angle.",
                    useful_points[0] if useful_points else "Move from scene to diagnosis so the article clearly advances.",
                ],
                "Grounded and interpretive",
                summary="Turn the opening tension into a sharper observation.",
                section_transition_hint="Once the reader recognizes the pattern, push toward a deeper turn or reframing.",
                evidence_refs=reference_names[:2],
            ),
            self._build_section(
                "s3",
                "Push the argument one step deeper",
                "Add the reframing, contrast, or method that keeps the article from sounding obvious",
                [
                    "Avoid repeating the diagnosis; introduce a sharper distinction, blind spot, or mindset shift.",
                    useful_points[1] if len(useful_points) > 1 else "Let this section feel like the article's turning point, not just another parallel point.",
                ],
                "Sharper, still human",
                summary="Create the section that makes the piece feel worth forwarding.",
                section_transition_hint="After the turning point, bring the reader toward a usable takeaway instead of staying abstract.",
                evidence_refs=reference_names[:2],
            ),
            self._build_section(
                "s4",
                "Land with a usable next move",
                "Convert the argument into a clear emotional or practical landing instead of a weak recap",
                [
                    "Give the reader one memorable line of takeaway and one realistic next move.",
                    "Close with emotional pressure, clarity, or action, not a generic summary.",
                ],
                "Supportive and actionable",
                summary="Finish with a closing that feels earned.",
                section_transition_hint="This is the landing section; do not reopen a new subtopic.",
                evidence_refs=reference_names[:1],
            ),
        ]
        outline = {
            "article_goal": f"Help {target_reader} understand and act on {selected_topic or selected_title}.",
            "why_this_topic": "This topic is timely enough to matter and close enough to the account's lane to own.",
            "strategic_angle": f"Use the {lane} lane to turn the topic into a sharper account-owned judgment.",
            "reference_basis": ", ".join(reference_names[:2]),
            "target_reader": str(target_reader),
            "content_lane": lane,
            "target_reader_takeaway": "Leave with one clearer perspective and one doable action.",
            "opening_hook": f"Start from a vivid moment or contradiction around {selected_topic or selected_title}, not a background lecture.",
            "emotional_arc": "recognition -> diagnosis -> turn -> landing",
            "sections": sections,
            "ending_cta": "Leave the reader with a sentence worth underlining and a next step worth taking.",
            "estimated_word_count": 1400,
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
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = self._resolve_reference_digest(input_data, query_plan)
        hot_items = hot_topics.get("hot_topics") if isinstance(hot_topics, dict) else []
        source_candidates = input_data.get("source_candidates") or []

        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
            "automation_plan_summary": account_context.get("automation_plan_summary") or "",
        }
        ops_snapshot = {
            "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
            "effective_mode": (ops_context.get("run_strategy") or {}).get("effective_mode") or "",
            "avoid_recent_topics": (ops_context.get("run_strategy") or {}).get("avoid_recent_topics") or [],
            "preferred_reference_source_ids": (ops_context.get("run_strategy") or {}).get("preferred_reference_source_ids") or [],
        }
        topic_snapshot = {
            "selected_topic": selected_topic,
            "selected_title": selected_title,
            "title_candidates": title_candidates,
            "hot_topics": hot_items[:3] if isinstance(hot_items, list) else [],
        }

        return "\n".join(
            [
                "Create a practical outline for a WeChat article.",
                "Think like a human editor planning a strong public-account draft before writing.",
                "",
                "PLANNING RULES",
                "- Make the opening_hook immediately usable as the article's opening paragraph seed.",
                f"- Stay locked to this exact topic/title pair: {selected_topic} / {selected_title}. If a section could fit another article, it is wrong.",
                "- why_this_topic must explain the strategic value of writing now for this account.",
                "- strategic_angle must say what judgment or tension makes this article feel owned by the account.",
                "- Give each section a distinct job: hook, diagnosis, turn, landing. Merge or split only if the topic truly needs it.",
                "- Sections should progress. Later sections must not feel like reordered duplicates of earlier ones.",
                "- The ending_cta should feel like a landing sentence or action prompt, not a soft recap.",
                "- Let reference-source style cues shape structure, but never copy their phrasing.",
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
                "TOPIC PACKAGE",
                article_assembler_service.to_pretty_json(topic_snapshot),
                "",
                "REFERENCE STYLE BRIEF",
                article_assembler_service.to_pretty_json(reference_digest),
                "",
                "SOURCE CANDIDATES",
                article_assembler_service.to_pretty_json(source_candidates[:5] if isinstance(source_candidates, list) else []),
                "",
                "RETURN CONTRACT",
                "- article_goal: one sentence on what the article tries to do for the reader.",
                "- why_this_topic: why this account should write this topic now.",
                "- strategic_angle: the account-owned way into the topic.",
                "- reference_basis: which source or digest pattern the outline is borrowing from.",
                "- target_reader: who this outline is really written for.",
                "- content_lane: the lane label that anchors the outline.",
                "- target_reader_takeaway: what should remain after reading.",
                "- opening_hook: 1-2 sentences, specific and non-generic.",
                "- emotional_arc: short phrase showing how the article should move emotionally.",
                "- sections: 3-5 sections, each with section_id, heading, purpose, summary, key_points, tone_hint, section_transition_hint, evidence_refs.",
                "- ending_cta: a closing landing sentence or action prompt.",
                "- estimated_word_count: practical long-form range for this topic.",
                "- summary: one-line outline summary.",
                "",
                "Return JSON with article_goal, why_this_topic, strategic_angle, reference_basis, target_reader, content_lane, target_reader_takeaway, opening_hook, emotional_arc, sections, ending_cta, estimated_word_count, summary.",
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

    def _normalize_outline(self, data: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
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
                        section_transition_hint=str(
                            item.get("section_transition_hint") or item.get("transition_hint") or ""
                        ).strip()
                        or None,
                        evidence_refs=item.get("evidence_refs") if isinstance(item.get("evidence_refs"), list) else [],
                    )
                )

        query_plan = self._resolve_query_plan(input_data)
        return {
            "article_goal": str(data.get("article_goal") or "").strip(),
            "why_this_topic": str(data.get("why_this_topic") or "").strip(),
            "strategic_angle": str(data.get("strategic_angle") or "").strip(),
            "reference_basis": str(data.get("reference_basis") or "").strip(),
            "target_reader": str(data.get("target_reader") or "").strip(),
            "content_lane": str(data.get("content_lane") or (query_plan.get("lane") or {}).get("label") or "").strip(),
            "target_reader_takeaway": str(data.get("target_reader_takeaway") or "").strip(),
            "opening_hook": str(data.get("opening_hook") or "").strip(),
            "emotional_arc": str(data.get("emotional_arc") or "").strip(),
            "sections": normalized_sections,
            "ending_cta": str(data.get("ending_cta") or "").strip(),
            "estimated_word_count": int(data.get("estimated_word_count") or 1200),
            "summary": str(data.get("summary") or data.get("article_goal") or "").strip(),
        }

    def _outline_matches_topic(
        self,
        outline: dict[str, Any],
        selected_topic: str,
        selected_title: str,
    ) -> bool:
        combined_parts = [
            outline.get("article_goal"),
            outline.get("why_this_topic"),
            outline.get("strategic_angle"),
            outline.get("target_reader_takeaway"),
            outline.get("opening_hook"),
            outline.get("ending_cta"),
            outline.get("summary"),
        ]
        for section in outline.get("sections", []) if isinstance(outline.get("sections"), list) else []:
            if not isinstance(section, dict):
                continue
            combined_parts.extend(
                [
                    section.get("heading"),
                    section.get("purpose"),
                    section.get("summary"),
                    " ".join(section.get("key_points") or []),
                ]
            )
        combined_text = " ".join(str(part or "") for part in combined_parts)
        return article_assembler_service.text_matches_topic(
            combined_text,
            selected_topic=selected_topic,
            selected_title=selected_title,
        )

    def _build_section(
        self,
        section_id: str,
        heading: str,
        purpose: str,
        key_points: list[Any],
        tone_hint: str,
        *,
        summary: str | None = None,
        section_transition_hint: str | None = None,
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
            "section_transition_hint": section_transition_hint,
            "evidence_refs": normalized_evidence,
        }
