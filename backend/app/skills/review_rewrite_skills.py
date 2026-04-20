"""Shared review and rewrite skills plus compatibility mixins."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service
from app.skills.base import BaseSkill, SkillResult


class _ReviewSupportMixin:
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

    def _resolve_reference_digest(self, input_data: dict[str, Any], query_plan: dict[str, Any]) -> dict[str, Any]:
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

    async def _run_generation(self, *, input_data: dict[str, Any], context: dict[str, Any], completion_callable):
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)
        node_timeout = context.get("node_timeout_seconds")
        if isinstance(node_timeout, (int, float)) and node_timeout > 0:
            llm_timeout = max(float(settings.llm_timeout), float(node_timeout) - 8.0)
        else:
            llm_timeout = float(settings.llm_timeout)
        response = await self.run_litellm_completion(
            context=context,
            completion_callable=completion_callable,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=llm_timeout,
        )
        return response.choices[0].message.content


class StyleReviewMixin(_ReviewSupportMixin):
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
"""

    async def review_style(self, *, input_data: dict[str, Any], context: dict[str, Any], completion_callable) -> dict[str, Any]:
        content = await self._run_generation(input_data=input_data, context=context, completion_callable=completion_callable)
        return self._normalize_review(self._parse_json(content))

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
        normalized_suggestions = [str(item).strip() for item in suggestions if str(item).strip()] if isinstance(suggestions, list) else []
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
        summary = str(data.get("summary") or "").strip() or (
            "Style review passed with only minor polish suggestions."
            if passed
            else "Style review found voice or phrasing issues that should be softened in rewrite."
        )
        return {"reviewer": "style_reviewer", "passed": passed, "score": normalized_score, "summary": summary, "issues": normalized_issues, "rewrite_suggestions": normalized_suggestions}

    def _normalize_severity(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in {"high", "medium", "low"} else "medium"

    def _normalize_issue_code(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        allowed_codes = {"style_drift", "account_voice_missed", "reference_style_missed", "ai_tone_heavy", "templated_transition", "repetitive_expression", "generic_opening", "weak_closing", "section_thin"}
        return text if text in allowed_codes else "style_drift"

    def _as_optional_text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None


class StructureReviewMixin(_ReviewSupportMixin):
    input_schema = {
        "type": "object",
        "properties": {
            "outline_plan": {"type": "object"},
            "section_drafts": {"type": "object"},
            "assembled_article": {"type": "object"},
            "content": {"type": "object"},
            "titles": {"type": "object"},
            "topics": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "query_plan": {"type": "object"},
            "reference_digest": {"type": "object"},
            "source_candidates": {"type": "array"},
        },
        "required": ["outline_plan", "assembled_article"],
    }

    output_schema = StyleReviewMixin.output_schema
    default_system_prompt = """You are a structure reviewer for WeChat long-form content.

Review the outline plan, section drafts, and assembled article.
Return strict JSON only.
"""

    async def review_structure(self, *, input_data: dict[str, Any], context: dict[str, Any], completion_callable) -> dict[str, Any]:
        content = await self._run_generation(input_data=input_data, context=context, completion_callable=completion_callable)
        return self._normalize_review(self._parse_json(content))

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        article = article_assembler_service.extract_article_payload(
            {
                "assembled_article": input_data.get("assembled_article"),
                "content": input_data.get("content"),
                "titles": input_data.get("titles"),
                "topics": input_data.get("topics"),
            }
        )
        outline_plan = input_data.get("outline_plan") or {}
        section_drafts = input_data.get("section_drafts") or {}
        ops_context = input_data.get("ops_context") or {}
        source_candidates = input_data.get("source_candidates") or []
        query_plan = self._resolve_query_plan(input_data)
        reference_digest = self._resolve_reference_digest(input_data, query_plan)
        outline_summary = article_assembler_service.summarize_outline_plan(outline_plan)
        section_summary = article_assembler_service.summarize_section_drafts(section_drafts)
        review_job = {
            "allowed_issue_codes": [
                "generic_opening",
                "weak_closing",
                "section_thin",
                "section_overweight",
                "outline_misaligned",
                "section_transition_flat",
                "reference_structure_missed",
            ],
            "issue_requirements": {
                "section_id": "Use the affected outline section when possible.",
                "message": "Say what structural job failed and how that hurts the article.",
                "suggestion": "Give a concrete revision direction.",
                "evidence_excerpt": "Short quote or outline mismatch note when useful.",
            },
        }
        return "\n".join(
            [
                "Review the article structure and outline fit.",
                "Keep the summary short. Use issues[] for the real diagnosis.",
                "",
                "OPS SNAPSHOT",
                article_assembler_service.to_pretty_json(
                    {
                        "effective_mode": (ops_context.get("run_strategy") or {}).get("effective_mode") or "",
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
                "OUTLINE SUMMARY",
                article_assembler_service.to_pretty_json(outline_summary),
                "",
                "SECTION SUMMARY",
                article_assembler_service.to_pretty_json(section_summary),
                "",
                "ASSEMBLED ARTICLE",
                article_assembler_service.to_pretty_json({"selected_title": article.get("selected_title") or "", "selected_topic": article.get("selected_topic") or "", "content_markdown": article.get("content_markdown") or ""}),
                "",
                "OUTPUT CONTRACT",
                article_assembler_service.to_pretty_json(review_job),
                "",
                "Return JSON with reviewer, passed, score, summary, issues, rewrite_suggestions.",
            ]
        )

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
        normalized_suggestions = [str(item).strip() for item in suggestions if str(item).strip()] if isinstance(suggestions, list) else []
        score = data.get("score")
        normalized_score = 0.82
        try:
            if score is not None:
                normalized_score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            normalized_score = 0.82
        passed = data.get("passed")
        if not isinstance(passed, bool):
            passed = not any(issue["severity"] in {"medium", "high"} for issue in normalized_issues)
        summary = str(data.get("summary") or "").strip() or (
            "Structure review passed with only light pacing suggestions."
            if passed
            else "Structure review found outline drift or weak sections that should be tightened."
        )
        return {"reviewer": "structure_reviewer", "passed": passed, "score": normalized_score, "summary": summary, "issues": normalized_issues, "rewrite_suggestions": normalized_suggestions}

    def _normalize_severity(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in {"high", "medium", "low"} else "medium"

    def _normalize_issue_code(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        allowed_codes = {"generic_opening", "weak_closing", "section_thin", "section_overweight", "outline_misaligned", "section_transition_flat", "reference_structure_missed"}
        return text if text in allowed_codes else "outline_misaligned"

    def _as_optional_text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None


class RewriteMixin(_ReviewSupportMixin):
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
"""

    async def rewrite_article(self, *, input_data: dict[str, Any], context: dict[str, Any], completion_callable) -> dict[str, Any]:
        content = await self._run_generation(input_data=input_data, context=context, completion_callable=completion_callable)
        return self._normalize_rewrite(self._parse_json(content))

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        article = article_assembler_service.extract_article_payload({"assembled_article": input_data.get("assembled_article"), "titles": input_data.get("titles"), "topics": input_data.get("topics")})
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
        account_snapshot = {"account_name": account_context.get("account_name") or "unknown", "tone_style": account_context.get("tone_style") or "", "positioning": account_context.get("positioning") or "", "audience": account_context.get("audience") or "", "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or ""}
        return "\n".join(
            [
                "Rewrite the article once using the reviewer findings.",
                "Do not perform a second-pass review. Make the strongest single rewrite you can.",
                "",
                "ACCOUNT SNAPSHOT",
                article_assembler_service.to_pretty_json(account_snapshot),
                "",
                "OPS SNAPSHOT",
                article_assembler_service.to_pretty_json({"effective_mode": (input_data.get("ops_context") or {}).get("run_strategy", {}).get("effective_mode") or "", "preferred_content_lane": (query_plan.get("lane") or {}).get("label") or ""}),
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
                article_assembler_service.to_pretty_json({"selected_title": article.get("selected_title") or "", "selected_topic": article.get("selected_topic") or "", "summary": article.get("summary") or "", "content_markdown": article.get("content_markdown") or ""}),
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
                "Return JSON with revised_content_markdown, revision_summary, fixed_issues, changed_sections, used_rewrite.",
            ]
        )

    def _normalize_rewrite(self, data: dict[str, Any]) -> dict[str, Any]:
        revised_content_markdown = str(data.get("revised_content_markdown") or data.get("content_markdown") or data.get("content") or "").strip()
        revision_summary = str(data.get("revision_summary") or data.get("summary") or "").strip()
        fixed_issues = [str(item).strip() for item in (data.get("fixed_issues") or []) if str(item).strip()] if isinstance(data.get("fixed_issues"), list) else []
        changed_sections = [str(item).strip() for item in (data.get("changed_sections") or []) if str(item).strip()] if isinstance(data.get("changed_sections"), list) else []
        used_rewrite = bool(revised_content_markdown) if not isinstance(data.get("used_rewrite"), bool) else data.get("used_rewrite")
        if not revision_summary:
            revision_summary = "Applied a single rewrite pass to tighten style and structure." if used_rewrite else "Rewrite skipped."
        return {"used_rewrite": used_rewrite, "revised_content_markdown": revised_content_markdown, "revised_content_html": self._optional_text(data.get("revised_content_html") or data.get("content_html")), "revision_summary": revision_summary, "summary": revision_summary, "fixed_issues": fixed_issues, "changed_sections": changed_sections, "content_markdown": revised_content_markdown}

    def _optional_text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _collect_review_focus(self, style_review: dict[str, Any], structure_review: dict[str, Any], review_results: list[Any]) -> dict[str, Any]:
        normalized_reviews = [article_assembler_service.summarize_review_result(style_review), article_assembler_service.summarize_review_result(structure_review)]
        for item in review_results:
            if isinstance(item, dict):
                summary = article_assembler_service.summarize_review_result(item)
                reviewer = summary.get("reviewer")
                if reviewer and reviewer not in {normalized_reviews[0].get("reviewer"), normalized_reviews[1].get("reviewer")}:
                    normalized_reviews.append(summary)
        priority_issues: list[dict[str, Any]] = []
        for review in normalized_reviews:
            for issue in review.get("issues", []):
                if isinstance(issue, dict) and issue.get("severity") in {"high", "medium"}:
                    priority_issues.append(issue)
        return {"reviews": normalized_reviews, "priority_issues": priority_issues[:10]}


class _SkillRuntimeMixin:
    def get_system_prompt(self, context: dict[str, Any]) -> str:
        return context.get("system_prompt") or self.default_system_prompt

    def get_effective_model_config(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"provider_id": "dashscope", "model": settings.llm_model_name, "api_key": settings.llm_api_key, "base_url": settings.llm_api_base_url, "timeout": settings.llm_timeout}

    def get_litellm_completion_kwargs(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        config = self.get_effective_model_config(context)
        return {"model": config["model"], "api_key": config["api_key"], "base_url": config["base_url"], "custom_llm_provider": config["provider_id"]}

    async def run_litellm_completion(self, *, context: dict[str, Any], completion_callable, messages, timeout, **kwargs):
        return await completion_callable(messages=messages, timeout=timeout, **self.get_litellm_completion_kwargs(context), **kwargs)


class StyleReviewSkill(_SkillRuntimeMixin, BaseSkill, StyleReviewMixin):
    skill_id = "style_review_skill"
    name = "Style Review Skill"
    description = "Review article voice fit and generic AI-style drift."

    async def execute(self, input_data: dict) -> dict:
        context = input_data.get("_context") if isinstance(input_data.get("_context"), dict) else {}
        try:
            data = await self.review_style(input_data=input_data, context=context, completion_callable=litellm.acompletion)
            return SkillResult.success(self.skill_id, data).to_dict()
        except Exception as exc:
            return SkillResult.failure(self.skill_id, "LLM_ERROR", str(exc)).to_dict()


class StructureReviewSkill(_SkillRuntimeMixin, BaseSkill, StructureReviewMixin):
    skill_id = "structure_review_skill"
    name = "Structure Review Skill"
    description = "Review outline adherence, pacing, and section progression."

    async def execute(self, input_data: dict) -> dict:
        context = input_data.get("_context") if isinstance(input_data.get("_context"), dict) else {}
        try:
            data = await self.review_structure(input_data=input_data, context=context, completion_callable=litellm.acompletion)
            return SkillResult.success(self.skill_id, data).to_dict()
        except Exception as exc:
            return SkillResult.failure(self.skill_id, "LLM_ERROR", str(exc)).to_dict()


class RewriteSkill(_SkillRuntimeMixin, BaseSkill, RewriteMixin):
    skill_id = "rewrite_skill"
    name = "Rewrite Skill"
    description = "Apply a single rewrite pass using review findings."

    async def execute(self, input_data: dict) -> dict:
        context = input_data.get("_context") if isinstance(input_data.get("_context"), dict) else {}
        try:
            data = await self.rewrite_article(input_data=input_data, context=context, completion_callable=litellm.acompletion)
            return SkillResult.success(self.skill_id, data).to_dict()
        except Exception as exc:
            return SkillResult.failure(self.skill_id, "LLM_ERROR", str(exc)).to_dict()


style_review_skill = StyleReviewSkill()
structure_review_skill = StructureReviewSkill()
rewrite_skill = RewriteSkill()
