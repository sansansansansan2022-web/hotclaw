"""Structure reviewer agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service


class StructureReviewerAgent(BaseAgent):
    """Review outline adherence and article structure quality."""

    agent_id = "structure_reviewer_agent"
    name = "Structure Reviewer"
    description = "Review outline adherence, pacing, and closing strength."

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
        },
        "required": ["outline_plan", "assembled_article"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "reviewer": {"type": "string"},
            "passed": {"type": "boolean"},
            "score": {"type": "number"},
            "summary": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "severity": {"type": "string"},
                        "message": {"type": "string"},
                        "section_id": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                },
            },
            "rewrite_suggestions": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }

    default_system_prompt = """You are a structure reviewer for WeChat long-form content.

Review the outline plan, section drafts, and assembled article.
Return strict JSON only.

Focus on:
- whether the article follows the outline
- whether sections feel balanced and concrete
- whether the closing lands well
- whether any section feels thin or off-structure

Do not rewrite the article. Only review it.
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
            return self._success(self._normalize_review(data))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse structure review JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

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

        return "\n".join(
            [
                "Review the article structure and outline fit.",
                "",
                "OPS CONTEXT",
                f"- effective_mode: {(ops_context.get('run_strategy') or {}).get('effective_mode') or ''}",
                f"- preferred_content_lane: {(ops_context.get('run_strategy') or {}).get('preferred_content_lane') or ''}",
                "",
                "OUTLINE PLAN",
                str(outline_plan),
                "",
                "SECTION DRAFTS",
                str(section_drafts),
                "",
                "ASSEMBLED ARTICLE",
                f"- selected_title: {article.get('selected_title') or ''}",
                f"- selected_topic: {article.get('selected_topic') or ''}",
                f"- content_markdown: {article.get('content_markdown') or ''}",
                "",
                "Return JSON with reviewer, passed, score, summary, issues, rewrite_suggestions.",
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
                        "code": str(item.get("code") or "structure_issue").strip() or "structure_issue",
                        "severity": self._normalize_severity(item.get("severity")),
                        "message": message,
                        "description": message,
                        "section_id": self._as_optional_text(item.get("section_id")),
                        "location": self._as_optional_text(item.get("section_id")),
                        "title": self._as_optional_text(item.get("title")),
                        "suggestion": self._as_optional_text(item.get("suggestion")),
                    }
                )

        suggestions = data.get("rewrite_suggestions")
        normalized_suggestions = [
            str(item).strip() for item in suggestions if str(item).strip()
        ] if isinstance(suggestions, list) else []

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

        summary = str(data.get("summary") or "").strip()
        if not summary:
            summary = (
                "Structure review passed with only light pacing suggestions."
                if passed
                else "Structure review found outline drift or weak sections that should be tightened."
            )

        return {
            "reviewer": "structure_reviewer",
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

    def _as_optional_text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None
