"""Style reviewer agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service


class StyleReviewerAgent(BaseAgent):
    """Review article style fit before the rewrite stage."""

    agent_id = "style_reviewer_agent"
    name = "Style Reviewer"
    description = "Review style drift, AI tone, and voice consistency."

    input_schema = {
        "type": "object",
        "properties": {
            "assembled_article": {"type": "object"},
            "content": {"type": "object"},
            "titles": {"type": "object"},
            "topics": {"type": "object"},
            "profile": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "outline_plan": {"type": "object"},
            "section_drafts": {"type": "object"},
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
        },
        "required": ["assembled_article"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "reviewer": {"type": "string"},
            "passed": {"type": "boolean"},
            "score": {"type": "number"},
            "summary": {"type": "string"},
            "issues": {"type": "array"},
            "rewrite_suggestions": {"type": "array", "items": {"type": "string"}},
        },
    }

    default_system_prompt = """You are a style reviewer for WeChat long-form content.

Review the assembled article and return strict JSON only.

Focus on:
- tone drift from the account voice
- whether the article sounds too generic or AI-written
- whether the preferred reference-source style is actually visible in the draft
- repetitive phrasing, templated transitions, and weak opening/closing voice

Be concrete and conservative. Do not rewrite the article.
Flag only actionable problems and ground them in specific sections whenever possible.
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
            return self._success(self._normalize_review(self._parse_json(content)))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse style review JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        account_context = input_data.get("account_context") or {}
        profile = input_data.get("profile") or {}
        outline_plan = input_data.get("outline_plan") or {}
        section_drafts = input_data.get("section_drafts") or {}
        source_candidates = input_data.get("source_candidates") or []
        article = article_assembler_service.extract_article_payload(
            {
                "assembled_article": input_data.get("assembled_article"),
                "content": input_data.get("content"),
                "titles": input_data.get("titles"),
                "topics": input_data.get("topics"),
            }
        )
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = self._resolve_reference_digest(input_data, query_plan)
        outline_summary = article_assembler_service.summarize_outline_plan(outline_plan)
        section_summary = article_assembler_service.summarize_section_drafts(section_drafts)
        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
            "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or "",
        }
        review_job = {
            "allowed_issue_codes": [
                "style_drift",
                "account_voice_missed",
                "reference_style_missed",
                "ai_tone_heavy",
                "templated_transition",
                "repetitive_expression",
                "generic_opening",
                "weak_closing",
                "section_thin",
            ],
            "issue_requirements": {
                "section_id": "Set when you can localize the problem.",
                "message": "Describe what is wrong and why it hurts the article voice.",
                "suggestion": "Give one concrete edit direction rewrite can execute.",
                "evidence_excerpt": "Quote a short problematic phrase when useful.",
            },
        }

        return "\n".join(
            [
                "Review the article style fit and voice consistency.",
                "Keep the summary short. Spend the detail budget on issues that rewrite can act on directly.",
                "",
                "REVIEW RULES",
                "- Prefer 0-6 high-signal issues. Do not pad the review with vague praise.",
                "- Judge whether the draft sounds like this account and whether preferred references actually influenced the writing.",
                "- Catch AI-ish wording, templated transitions, repeated expressions, and lines that feel too generic for a real public-account writer.",
                "- If the opening or closing feels generic, flag it directly instead of hiding it under a broad summary.",
                "- Use source candidates and reference digest as the comparison target for style similarity, not as a fact-check source.",
                "",
                "ACCOUNT SNAPSHOT",
                article_assembler_service.to_pretty_json(account_snapshot),
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
                "OUTLINE SUMMARY",
                article_assembler_service.to_pretty_json(outline_summary),
                "",
                "SECTION SUMMARY",
                article_assembler_service.to_pretty_json(section_summary),
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
                "OUTPUT CONTRACT",
                article_assembler_service.to_pretty_json(review_job),
                "",
                "Return JSON with reviewer, passed, score, summary, issues, rewrite_suggestions.",
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

    def _normalize_review(self, data: dict[str, Any]) -> dict[str, Any]:
        issues = data.get("issues")
        normalized_issues: list[dict[str, Any]] = []
        if isinstance(issues, list):
            for item in issues:
                if not isinstance(item, dict):
                    continue
                message = str(item.get("message") or item.get("description") or "").strip()
                if not message:
                    continue
                normalized_issues.append(
                    {
                        "code": self._normalize_issue_code(item.get("code")),
                        "severity": self._normalize_severity(item.get("severity")),
                        "message": message,
                        "description": message,
                        "section_id": self._as_optional_text(item.get("section_id")),
                        "location": self._as_optional_text(item.get("section_id")),
                        "title": self._as_optional_text(item.get("title")),
                        "suggestion": self._as_optional_text(item.get("suggestion")),
                        "evidence_excerpt": self._as_optional_text(item.get("evidence_excerpt")),
                    }
                )

        suggestions = data.get("rewrite_suggestions")
        normalized_suggestions = [
            str(item).strip() for item in suggestions if str(item).strip()
        ] if isinstance(suggestions, list) else []

        score = data.get("score")
        normalized_score = 0.85
        try:
            if score is not None:
                normalized_score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            normalized_score = 0.85

        passed = data.get("passed")
        if not isinstance(passed, bool):
            passed = not any(issue["severity"] in {"medium", "high"} for issue in normalized_issues)

        summary = str(data.get("summary") or "").strip()
        if not summary:
            summary = (
                "Style review passed with only minor polish suggestions."
                if passed
                else "Style review found voice or phrasing issues that should be softened in rewrite."
            )

        return {
            "reviewer": "style_reviewer",
            "passed": passed,
            "score": normalized_score,
            "summary": summary,
            "issues": normalized_issues,
            "rewrite_suggestions": normalized_suggestions,
        }

    def _normalize_severity(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"high", "medium", "low"}:
            return text
        return "medium"

    def _normalize_issue_code(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        allowed_codes = {
            "style_drift",
            "account_voice_missed",
            "reference_style_missed",
            "ai_tone_heavy",
            "templated_transition",
            "repetitive_expression",
            "generic_opening",
            "weak_closing",
            "section_thin",
        }
        if text in allowed_codes:
            return text
        return "style_drift"

    def _as_optional_text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None
