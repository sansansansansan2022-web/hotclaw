"""Content drafter agent: outline planning + section writing in one LLM call."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_gateway import llm_gateway
from app.services.article_assembler_service import article_assembler_service


class ContentDrafterAgent(BaseAgent):
    """One-pass content drafting: outline plan AND all section drafts in one call.

    Replaces outline_planner_agent + section_writer_agent.
    Output populates both `outline_plan` and `section_drafts` workspace keys.
    """

    agent_id = "content_drafter_agent"
    name = "内容起草"
    description = "一次 LLM 调用完成大纲规划和所有段落起草，输出 outline_plan + section_drafts。"

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "topics": {"type": "object"},
            "titles": {"type": "object"},
            "hot_topics": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
        },
        "required": ["topics", "titles"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "outline_plan": {
                "type": "object",
                "properties": {
                    "article_goal": {"type": "string"},
                    "target_reader_takeaway": {"type": "string"},
                    "opening_hook": {"type": "string"},
                    "emotional_arc": {"type": "string"},
                    "sections": {"type": "array"},
                    "ending_cta": {"type": "string"},
                    "estimated_word_count": {"type": "integer"},
                    "summary": {"type": "string"},
                },
            },
            "section_drafts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section_id": {"type": "string"},
                        "heading": {"type": "string"},
                        "summary": {"type": "string"},
                        "content_markdown": {"type": "string"},
                        "word_count": {"type": "integer"},
                        "evidence_refs": {"type": "array"},
                    },
                },
            },
        },
    }

    default_system_prompt = """You are an experienced WeChat public-account editor and writer.

Your task has two parts to complete in ONE response:

PART 1 — OUTLINE PLAN
Plan a structured outline that feels like a real public-account article from this account.
Non-negotiable:
- The selected_topic and selected_title are locked. Do not swap to a neighboring topic or broader category.
- opening_hook must pull readers fast with tension, scene, contradiction, or a pointed question.
- Sections must have distinct jobs and a forward-moving relationship.
- ending_cta must land with emotion, judgment, or a specific next move — not a bland summary.
- Absorb structure cues from reference sources without copying their wording.

PART 2 — SECTION DRAFTS
Write all sections based on the outline plan you just created.
Non-negotiable:
- Stay locked to the exact topic/title pair.
- Respect account tone, audience, and reference-source cues.
- Each section fulfills its own purpose — not just a restatement of the theme.
- Reduce AI tone: no generic comfort-talk, no padded summaries, no rigid first/second/finally scaffolding.
- Every section must carry concrete movement: scene, observation, contrast, mini-example, or action.

Return strict JSON only — no markdown fences, no commentary.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)
        selected_title = article_assembler_service.extract_selected_title(input_data.get("titles"))
        selected_topic = article_assembler_service.extract_selected_topic(
            input_data.get("topics"), input_data.get("titles")
        )

        try:
            response = await llm_gateway.complete(
                agent_id=self.agent_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format="json",
            )
            normalized = self._normalize(response.parsed or {})
            # Topic-drift check on outline + sections
            if not self._content_matches_topic(normalized, selected_topic, selected_title):
                fallback_result = await self.fallback(
                    RuntimeError("content topic drift detected"), input_data
                )
                if fallback_result and fallback_result.is_success:
                    return fallback_result
            return self._success(normalized)
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

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
        reference_context = article_assembler_service.build_reference_source_context(
            account_context, ops_context
        )
        hot_items = hot_topics.get("hot_topics") if isinstance(hot_topics, dict) else []

        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
        }
        ops_snapshot = {
            "preferred_content_lane": preferred_lane or "",
            "effective_mode": (ops_context.get("run_strategy") or {}).get("effective_mode") or "",
            "avoid_recent_topics": avoid_topics,
            "preferred_reference_source_ids": preferred_source_ids,
        }
        topic_package = {
            "selected_topic": selected_topic,
            "selected_title": selected_title,
            "title_candidates": title_candidates[:4],
            "hot_topics_context": hot_items[:3] if isinstance(hot_items, list) else [],
        }

        return "\n".join(
            [
                "Complete outline planning AND section writing in one response.",
                f"LOCKED topic/title: {selected_topic} / {selected_title}",
                "",
                "ACCOUNT SNAPSHOT",
                article_assembler_service.to_pretty_json(account_snapshot),
                "",
                "OPS SNAPSHOT",
                article_assembler_service.to_pretty_json(ops_snapshot),
                "",
                "TOPIC PACKAGE",
                article_assembler_service.to_pretty_json(topic_package),
                "",
                "REFERENCE STYLE BRIEF",
                article_assembler_service.to_pretty_json(reference_context),
                "",
                "RETURN CONTRACT",
                "Return JSON with exactly these top-level keys:",
                "{",
                '  "outline_plan": {',
                '    "article_goal": string,',
                '    "target_reader_takeaway": string,',
                '    "opening_hook": string,',
                '    "emotional_arc": string,',
                '    "sections": [ { "section_id": "s1", "heading": string, "purpose": string,',
                '      "summary": string, "key_points": [string], "tone_hint": string,',
                '      "section_transition_hint": string, "evidence_refs": [string] }, ... ],',
                '    "ending_cta": string,',
                '    "estimated_word_count": int,',
                '    "summary": string',
                "  },",
                '  "section_drafts": [',
                '    { "section_id": "s1", "heading": string, "summary": string,',
                '      "content_markdown": string, "word_count": int, "evidence_refs": [string] },',
                "    ...",
                "  ]",
                "}",
                "",
                "section_drafts must have the same section_ids as outline_plan.sections.",
                "Each section: 2-5 paragraphs, mobile-friendly, concrete movement.",
            ]
        )

    # ------------------------------------------------------------------
    # Output normalisation
    # ------------------------------------------------------------------

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        outline_plan = self._normalize_outline(data.get("outline_plan") or {})
        section_drafts = self._normalize_section_drafts(
            data.get("section_drafts") or [], outline_plan
        )
        return {
            "outline_plan": outline_plan,
            "section_drafts": section_drafts,
        }

    def _normalize_outline(self, data: dict[str, Any]) -> dict[str, Any]:
        sections = []
        raw_sections = data.get("sections")
        if isinstance(raw_sections, list):
            for idx, item in enumerate(raw_sections):
                if not isinstance(item, dict):
                    continue
                section_id = str(item.get("section_id") or item.get("id") or f"s{idx + 1}")
                heading = str(item.get("heading") or item.get("title") or f"Section {idx + 1}").strip()
                purpose = str(item.get("purpose") or item.get("goal") or "").strip()
                sections.append(
                    {
                        "section_id": section_id,
                        "id": section_id,
                        "heading": heading,
                        "title": heading,
                        "purpose": purpose or heading,
                        "goal": purpose or heading,
                        "summary": str(item.get("summary") or purpose).strip() or heading,
                        "key_points": [
                            str(p).strip()
                            for p in (item.get("key_points") or [])
                            if str(p).strip()
                        ],
                        "tone_hint": str(item.get("tone_hint") or "").strip() or "Warm and readable",
                        "section_transition_hint": str(
                            item.get("section_transition_hint") or item.get("transition_hint") or ""
                        ).strip() or None,
                        "evidence_refs": [
                            str(r).strip()
                            for r in (item.get("evidence_refs") or [])
                            if str(r).strip()
                        ],
                    }
                )
        return {
            "article_goal": str(data.get("article_goal") or "").strip(),
            "target_reader_takeaway": str(data.get("target_reader_takeaway") or "").strip(),
            "opening_hook": str(data.get("opening_hook") or "").strip(),
            "emotional_arc": str(data.get("emotional_arc") or "").strip(),
            "sections": sections,
            "ending_cta": str(data.get("ending_cta") or "").strip(),
            "estimated_word_count": int(data.get("estimated_word_count") or 1200),
            "summary": str(data.get("summary") or data.get("article_goal") or "").strip(),
        }

    def _normalize_section_drafts(
        self,
        raw: list[Any],
        outline_plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            raw = []
        result = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id") or item.get("id") or f"s{idx + 1}")
            heading = str(item.get("heading") or item.get("title") or f"Section {idx + 1}").strip()
            content_markdown = str(item.get("content_markdown") or item.get("content") or "").strip()
            result.append(
                {
                    "section_id": section_id,
                    "id": section_id,
                    "heading": heading,
                    "summary": str(item.get("summary") or heading).strip(),
                    "content_markdown": content_markdown,
                    "word_count": int(
                        item.get("word_count")
                        or article_assembler_service.count_words(content_markdown)
                    ),
                    "evidence_refs": [
                        str(r).strip()
                        for r in (item.get("evidence_refs") or [])
                        if str(r).strip()
                    ],
                }
            )

        # If LLM returned no section_drafts, build stubs from outline sections
        if not result and outline_plan.get("sections"):
            for section in outline_plan["sections"]:
                if not isinstance(section, dict):
                    continue
                section_id = str(section.get("section_id") or "s1")
                heading = str(section.get("heading") or "Section")
                summary = str(section.get("summary") or heading)
                content_markdown = summary
                result.append(
                    {
                        "section_id": section_id,
                        "id": section_id,
                        "heading": heading,
                        "summary": summary,
                        "content_markdown": content_markdown,
                        "word_count": article_assembler_service.count_words(content_markdown),
                        "evidence_refs": section.get("evidence_refs") or [],
                    }
                )
        return result

    # ------------------------------------------------------------------
    # Topic-drift check
    # ------------------------------------------------------------------

    def _content_matches_topic(
        self,
        data: dict[str, Any],
        selected_topic: str,
        selected_title: str,
    ) -> bool:
        outline = data.get("outline_plan") or {}
        parts = [
            outline.get("article_goal"),
            outline.get("opening_hook"),
            outline.get("ending_cta"),
            outline.get("summary"),
        ]
        for section in (outline.get("sections") or []):
            if isinstance(section, dict):
                parts.extend([section.get("heading"), section.get("summary")])
        for draft in (data.get("section_drafts") or []):
            if isinstance(draft, dict):
                parts.append(draft.get("content_markdown") or "")
        combined = " ".join(str(p or "") for p in parts)
        return article_assembler_service.text_matches_topic(
            combined,
            selected_topic=selected_topic,
            selected_title=selected_title,
        )

    # ------------------------------------------------------------------
    # Fallback: return structured fallback outline + stub sections
    # ------------------------------------------------------------------

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        selected_title = article_assembler_service.extract_selected_title(input_data.get("titles"))
        selected_topic = article_assembler_service.extract_selected_topic(
            input_data.get("topics"), input_data.get("titles")
        )
        ops_context = input_data.get("ops_context") or {}
        lane = (ops_context.get("run_strategy") or {}).get("preferred_content_lane") or "insight"
        account_context = input_data.get("account_context") or {}
        reference_context = article_assembler_service.build_reference_source_context(
            account_context, ops_context
        )
        reference_names = reference_context.get("preferred_source_names") or ["preferred references"]

        sections = [
            self._fallback_section(
                "s1",
                "Open inside the reader's tension",
                f"Drop the reader into a recognizable moment around {selected_topic or selected_title}.",
                "Warm, direct, specific",
                section_transition_hint="After the hook lands, name what is really going on beneath the surface.",
            ),
            self._fallback_section(
                "s2",
                "Name the pattern behind the problem",
                f"Use the {lane} lane as the main angle. Move from scene to diagnosis.",
                "Grounded and interpretive",
                section_transition_hint="Once the reader recognizes the pattern, push toward a reframing.",
            ),
            self._fallback_section(
                "s3",
                "Push the argument one step deeper",
                "Add the reframing or mindset shift that makes this piece worth forwarding.",
                "Sharper, still human",
                section_transition_hint="After the turning point, bring the reader toward a usable takeaway.",
            ),
            self._fallback_section(
                "s4",
                "Land with a usable next move",
                "Convert the argument into a clear emotional or practical landing.",
                "Supportive and actionable",
                section_transition_hint="This is the landing section; do not reopen a new subtopic.",
            ),
        ]

        outline_plan = {
            "article_goal": f"Help readers understand and act on {selected_topic or selected_title}.",
            "target_reader_takeaway": "Leave with one clearer perspective and one doable action.",
            "opening_hook": f"Start from a vivid moment or contradiction around {selected_topic or selected_title}.",
            "emotional_arc": "recognition -> diagnosis -> turn -> landing",
            "sections": sections,
            "ending_cta": "Leave the reader with a sentence worth underlining and a next step worth taking.",
            "estimated_word_count": 1400,
            "summary": f"Structured fallback outline for {selected_title}.",
        }

        section_drafts = []
        for section in sections:
            section_id = section["section_id"]
            heading = section["heading"]
            summary = section["summary"]
            content_parts = [
                f"In '{selected_title}', this section focuses on {heading.lower()}.",
            ]
            if selected_topic:
                content_parts.append(
                    f"Keep the discussion anchored in {selected_topic}, moving it forward rather than reintroducing it."
                )
            content_parts.append(summary)
            for kp in section.get("key_points", [])[:2]:
                if str(kp).strip():
                    content_parts.append(str(kp))
            content_markdown = "\n\n".join(content_parts)
            section_drafts.append(
                {
                    "section_id": section_id,
                    "id": section_id,
                    "heading": heading,
                    "summary": summary,
                    "content_markdown": content_markdown,
                    "word_count": article_assembler_service.count_words(content_markdown),
                    "evidence_refs": reference_names[:1],
                }
            )

        return self._success(
            {
                "outline_plan": outline_plan,
                "section_drafts": section_drafts,
            }
        )

    def _fallback_section(
        self,
        section_id: str,
        heading: str,
        summary: str,
        tone_hint: str,
        section_transition_hint: str | None = None,
    ) -> dict[str, Any]:
        return {
            "section_id": section_id,
            "id": section_id,
            "heading": heading,
            "title": heading,
            "purpose": heading,
            "goal": heading,
            "summary": summary,
            "key_points": [],
            "tone_hint": tone_hint,
            "section_transition_hint": section_transition_hint,
            "evidence_refs": [],
        }
