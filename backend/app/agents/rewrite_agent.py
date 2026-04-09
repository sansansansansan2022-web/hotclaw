"""Rewrite agent for the structured article pipeline."""

from __future__ import annotations

import json
from typing import Any

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.services.article_assembler_service import article_assembler_service


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
- preserve the article topic, title, and main argument
- fix the most important style and structure issues first
- do not invent sources or facts
- keep the article readable on mobile
- do only one rewrite pass
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
            return self._success(self._normalize_rewrite(data))
        except json.JSONDecodeError as exc:
            return self._failure("JSON_PARSE_ERROR", f"Failed to parse rewrite JSON: {exc}")
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

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
        ops_context = input_data.get("ops_context") or {}
        account_context = input_data.get("account_context") or {}

        return "\n".join(
            [
                "Rewrite the article once using the reviewer findings.",
                "",
                "ACCOUNT",
                f"- name: {account_context.get('account_name') or 'unknown'}",
                f"- tone: {account_context.get('tone_style') or ''}",
                f"- positioning: {account_context.get('positioning') or ''}",
                "",
                "OPS CONTEXT",
                f"- effective_mode: {(ops_context.get('run_strategy') or {}).get('effective_mode') or ''}",
                f"- preferred_content_lane: {(ops_context.get('run_strategy') or {}).get('preferred_content_lane') or ''}",
                "",
                "ARTICLE",
                f"- selected_title: {article.get('selected_title') or ''}",
                f"- selected_topic: {article.get('selected_topic') or ''}",
                f"- summary: {article.get('summary') or ''}",
                f"- content_markdown: {article.get('content_markdown') or ''}",
                "",
                "OUTLINE AND DRAFTS",
                f"- outline_plan: {outline_plan}",
                f"- section_drafts: {section_drafts}",
                "",
                "STYLE REVIEW",
                str(style_review),
                "",
                "STRUCTURE REVIEW",
                str(structure_review),
                "",
                "ALL REVIEW RESULTS",
                str(review_results),
                "",
                "Return JSON with revised_content_markdown, revision_summary, fixed_issues, changed_sections, used_rewrite.",
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

    def _normalize_rewrite(self, data: dict[str, Any]) -> dict[str, Any]:
        revised_content_markdown = str(
            data.get("revised_content_markdown")
            or data.get("content_markdown")
            or data.get("content")
            or ""
        ).strip()
        revision_summary = str(
            data.get("revision_summary")
            or data.get("summary")
            or ""
        ).strip()
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

        used_rewrite = bool(revised_content_markdown) if not isinstance(data.get("used_rewrite"), bool) else data.get("used_rewrite")
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
