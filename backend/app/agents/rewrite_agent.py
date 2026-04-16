"""Rewrite agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service


class RewriteAgent(BaseAgent):
    """Perform a single best-effort rewrite pass after review."""

    agent_id = "rewrite_agent"
    name = "Rewrite Agent"
    description = "Apply one revision pass using reviewer findings."

    input_schema = {
        "type": "object",
        "properties": {
            "titles": {"type": "object"},
            "topics": {"type": "object"},
            "outline_plan": {"type": "object"},
            "section_drafts": {"type": "object"},
            "assembled_article": {"type": "object"},
            "style_review": {"type": "object"},
            "structure_review": {"type": "object"},
            "review_results": {"type": "array"},
            "ops_context": {"type": "object"},
            "account_context": {"type": "object"},
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
        },
        "required": ["assembled_article"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "revised_content_markdown": {"type": "string"},
            "revised_content_html": {"type": "string"},
            "revision_summary": {"type": "string"},
            "fixed_issues": {"type": "array", "items": {"type": "string"}},
            "changed_sections": {"type": "array", "items": {"type": "string"}},
            "used_rewrite": {"type": "boolean"},
        },
    }

    default_system_prompt = """You are a rewrite agent for WeChat long-form content.

Use the assembled article and reviewer findings to make one revision pass.
Return strict JSON only.

Requirements:
- preserve the article topic, title, outline intent, and main argument
- fix the most important style and structure issues first
- pull the voice closer to the account and preferred reference sources when style drift is flagged
- do not invent sources or facts
- keep the article readable on mobile
- do only one rewrite pass
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

        try:
            node_timeout = context.get("node_timeout_seconds")
            if isinstance(node_timeout, (int, float)) and node_timeout > 0:
                llm_timeout = max(float(settings.llm_timeout), float(node_timeout) - 8.0)
            else:
                llm_timeout = float(settings.llm_timeout)

            response = await self.run_litellm_completion(
                context=context,
                completion_callable=litellm.acompletion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=llm_timeout,
            )
            content = response.choices[0].message.content
            return self._attach_runtime_trace(self._success(self._normalize_rewrite(self._parse_json(content))), context)
        except json.JSONDecodeError as exc:
            return self._attach_runtime_trace(
                self._failure("JSON_PARSE_ERROR", f"Failed to parse rewrite JSON: {exc}"),
                context,
            )
        except Exception as exc:
            return self._attach_runtime_trace(self._failure("LLM_ERROR", str(exc)), context)

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        article = article_assembler_service.extract_article_payload(
            {
                "assembled_article": input_data.get("assembled_article"),
                "titles": input_data.get("titles"),
                "topics": input_data.get("topics"),
            }
        )
        style_review = input_data.get("style_review") or {}
        structure_review = input_data.get("structure_review") or {}
        review_results = input_data.get("review_results") or []
        outline_plan = input_data.get("outline_plan") or {}
        section_drafts = input_data.get("section_drafts") or {}
        source_candidates = input_data.get("source_candidates") or []
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = self._resolve_reference_digest(input_data, query_plan)
        outline_summary = article_assembler_service.summarize_outline_plan(outline_plan)
        section_summary = article_assembler_service.summarize_section_drafts(section_drafts)
        review_focus = self._collect_review_focus(style_review, structure_review, review_results)
        account_context = input_data.get("account_context") or {}
        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "tone_style": account_context.get("tone_style") or "",
            "positioning": account_context.get("positioning") or "",
            "audience": account_context.get("audience") or "",
            "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
        }

        return "\n".join(
            [
                "Rewrite the article once using the reviewer findings.",
                "Do not perform a second-pass review. Make the strongest single rewrite you can.",
                "",
                "REWRITE PRIORITIES",
                "- Fix medium/high reviewer issues before touching minor polish.",
                "- If the style is generic or templated, replace the phrasing with something more specific, human, and account-consistent.",
                "- If a section is thin or off-purpose, deepen it in place instead of drifting into a new topic.",
                "- If opening or closing issues are flagged, rewrite those parts decisively so the article starts and lands with intent.",
                "- Absorb reference-source cadence and framing cues without copying any reference sentences.",
                "",
                "ACCOUNT SNAPSHOT",
                article_assembler_service.to_pretty_json(account_snapshot),
                "",
                "OPS SNAPSHOT",
                article_assembler_service.to_pretty_json(
                    {
                        "effective_mode": (input_data.get("ops_context") or {}).get("run_strategy", {}).get("effective_mode") or "",
                        "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
                    }
                ),
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
                "ARTICLE",
                article_assembler_service.to_pretty_json(
                    {
                        "selected_title": article.get("selected_title") or "",
                        "selected_topic": article.get("selected_topic") or "",
                        "summary": article.get("summary") or "",
                        "content_markdown": article.get("content_markdown") or "",
                    }
                ),
                "",
                "OUTLINE SUMMARY",
                article_assembler_service.to_pretty_json(outline_summary),
                "",
                "SECTION SUMMARY",
                article_assembler_service.to_pretty_json(section_summary),
                "",
                "REVIEW FOCUS",
                article_assembler_service.to_pretty_json(review_focus),
                "",
                "RETURN CONTRACT",
                "- Return JSON with revised_content_markdown, revision_summary, fixed_issues, changed_sections, used_rewrite.",
                "- fixed_issues should list the issue codes you actually addressed.",
                "- changed_sections should use section_ids when the rewrite was localized.",
                "- revision_summary should explain the main improvements in one or two sentences.",
                "",
                "Return JSON with revised_content_markdown, revision_summary, fixed_issues, changed_sections, used_rewrite.",
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

    def _normalize_rewrite(self, data: dict[str, Any]) -> dict[str, Any]:
        revised_content_markdown = str(
            data.get("revised_content_markdown")
            or data.get("content_markdown")
            or data.get("content")
            or ""
        ).strip()
        revision_summary = str(data.get("revision_summary") or data.get("summary") or "").strip()
        fixed_issues = [
            str(item).strip()
            for item in (data.get("fixed_issues") or [])
            if str(item).strip()
        ] if isinstance(data.get("fixed_issues"), list) else []
        changed_sections = [
            str(item).strip()
            for item in (data.get("changed_sections") or [])
            if str(item).strip()
        ] if isinstance(data.get("changed_sections"), list) else []

        used_rewrite = (
            bool(revised_content_markdown)
            if not isinstance(data.get("used_rewrite"), bool)
            else data.get("used_rewrite")
        )
        if not revision_summary:
            revision_summary = (
                "Applied a single rewrite pass to tighten style and structure."
                if used_rewrite
                else "Rewrite skipped."
            )

        return {
            "used_rewrite": used_rewrite,
            "revised_content_markdown": revised_content_markdown,
            "revised_content_html": self._optional_text(data.get("revised_content_html") or data.get("content_html")),
            "revision_summary": revision_summary,
            "summary": revision_summary,
            "fixed_issues": fixed_issues,
            "changed_sections": changed_sections,
            "content_markdown": revised_content_markdown,
        }

    def _optional_text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _collect_review_focus(
        self,
        style_review: dict[str, Any],
        structure_review: dict[str, Any],
        review_results: list[Any],
    ) -> dict[str, Any]:
        normalized_reviews = [
            article_assembler_service.summarize_review_result(style_review),
            article_assembler_service.summarize_review_result(structure_review),
        ]
        for item in review_results:
            if isinstance(item, dict):
                summary = article_assembler_service.summarize_review_result(item)
                reviewer = summary.get("reviewer")
                if reviewer and reviewer not in {
                    normalized_reviews[0].get("reviewer"),
                    normalized_reviews[1].get("reviewer"),
                }:
                    normalized_reviews.append(summary)

        priority_issues: list[dict[str, Any]] = []
        for review in normalized_reviews:
            for issue in review.get("issues", []):
                if not isinstance(issue, dict):
                    continue
                if issue.get("severity") in {"high", "medium"}:
                    priority_issues.append(issue)

        return {
            "reviews": normalized_reviews,
            "priority_issues": priority_issues[:10],
        }
