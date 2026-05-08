"""Editorial review agent: style + structure + compliance in one LLM call."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_gateway import llm_gateway
from app.services.article_assembler_service import article_assembler_service


class EditorialReviewAgent(BaseAgent):
    """Single-pass editorial review combining style, structure and compliance.

    Replaces the three sequential style_reviewer / structure_reviewer / audit
    nodes with one LLM call.  The output is normalised so that downstream
    workspace keys (style_review, structure_review, audit_result, review_results)
    remain unchanged — rewrite_agent reads those and is not affected.
    """

    agent_id = "editorial_review_agent"
    name = "编辑审核"
    description = "一次 LLM 调用完成风格、结构、合规三维审核，输出合并审核报告。"

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
        },
        "required": ["assembled_article"],
    }

    _STYLE_ISSUE_CODES = {
        "style_drift",
        "reference_style_missed",
        "templated_tone",
        "repetitive_expression",
        "generic_opening",
        "weak_closing",
        "section_thin",
    }
    _STRUCTURE_ISSUE_CODES = {
        "generic_opening",
        "weak_closing",
        "section_thin",
        "section_overweight",
        "outline_misaligned",
        "section_transition_flat",
        "reference_structure_missed",
    }
    _AUDIT_ISSUE_TYPES = {
        "sensitive_word",
        "political_risk",
        "false_info",
        "exaggeration",
        "clickbait",
        "tone_mismatch",
        "quality",
    }

    output_schema = {
        "type": "object",
        "properties": {
            "editorial_passed": {"type": "boolean"},
            "style": {"type": "object"},
            "structure": {"type": "object"},
            "audit": {"type": "object"},
            "combined_rewrite_suggestions": {"type": "array", "items": {"type": "string"}},
        },
    }

    default_system_prompt = """\
你是资深微信公众号内容编辑，负责对文章进行三维一体审核并输出 JSON。

## 三维任务
1. **风格审核（style）**：语气一致性、AI 感、口癖检测、参考源风格渗透
2. **结构审核（structure）**：大纲符合度、节奏、开头/结尾张力、段落衔接
3. **合规审核（audit）**：敏感词、虚假信息、绝对化宣传、标题党

## 输出规范
必须返回如下 JSON，不得输出其他内容：
{
  "editorial_passed": bool,          // 三维全部通过时为 true
  "style": {
    "reviewer": "style_reviewer",
    "passed": bool,
    "score": float,                  // 0.0 ~ 1.0
    "summary": string,
    "issues": [
      {
        "code": string,              // 限：style_drift/reference_style_missed/templated_tone/repetitive_expression/generic_opening/weak_closing/section_thin
        "severity": string,          // low/medium/high
        "message": string,
        "section_id": string|null,
        "suggestion": string|null,
        "evidence_excerpt": string|null
      }
    ],
    "rewrite_suggestions": [string]
  },
  "structure": {
    "reviewer": "structure_reviewer",
    "passed": bool,
    "score": float,
    "summary": string,
    "issues": [
      {
        "code": string,              // 限：generic_opening/weak_closing/section_thin/section_overweight/outline_misaligned/section_transition_flat/reference_structure_missed
        "severity": string,
        "message": string,
        "section_id": string|null,
        "suggestion": string|null,
        "evidence_excerpt": string|null
      }
    ],
    "rewrite_suggestions": [string]
  },
  "audit": {
    "passed": bool,
    "risk_level": string,            // low/medium/high
    "issues": [
      {
        "type": string,              // sensitive_word/political_risk/false_info/exaggeration/clickbait/tone_mismatch/quality
        "description": string,
        "severity": string,
        "location": string
      }
    ],
    "overall_comment": string
  },
  "combined_rewrite_suggestions": [string]   // 合并自 style+structure 的优先建议
}
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        system_prompt = self.get_system_prompt(context)
        user_prompt = self._build_user_prompt(input_data)

        try:
            response = await llm_gateway.complete(
                agent_id=self.agent_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format="json",
            )
            return self._success(self._normalize(response.parsed or {}))
        except Exception as exc:
            return self._failure("LLM_ERROR", str(exc))

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_user_prompt(self, input_data: dict[str, Any]) -> str:
        account_context = input_data.get("account_context") or {}
        profile = input_data.get("profile") or {}
        ops_context = input_data.get("ops_context") or {}
        outline_plan = input_data.get("outline_plan") or {}
        section_drafts = input_data.get("section_drafts") or {}

        article = article_assembler_service.extract_article_payload(
            {
                "assembled_article": input_data.get("assembled_article"),
                "content": input_data.get("content"),
                "titles": input_data.get("titles"),
                "topics": input_data.get("topics"),
            }
        )
        reference_context = article_assembler_service.build_reference_source_context(
            account_context, ops_context
        )
        outline_summary = article_assembler_service.summarize_outline_plan(outline_plan)
        section_summary = article_assembler_service.summarize_section_drafts(section_drafts)

        titles_data = input_data.get("titles") or {}
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []

        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "domain": profile.get("domain") or "",
            "content_strategy": account_context.get("content_strategy") or "",
            "preferred_content_lane": (ops_context.get("run_strategy") or {}).get("preferred_content_lane") or "",
        }

        parts = [
            "请对以下文章进行三维一体编辑审核，严格按系统提示中的 JSON 结构输出。",
            "",
            "ACCOUNT SNAPSHOT",
            article_assembler_service.to_pretty_json(account_snapshot),
            "",
            "REFERENCE STYLE BRIEF",
            article_assembler_service.to_pretty_json(reference_context),
            "",
            "OUTLINE SUMMARY",
            article_assembler_service.to_pretty_json(outline_summary),
            "",
            "SECTION SUMMARY",
            article_assembler_service.to_pretty_json(section_summary),
            "",
            "CANDIDATE TITLES",
            article_assembler_service.to_pretty_json(
                [t.get("text", "") for t in title_list[:3]] if isinstance(title_list, list) else []
            ),
            "",
            "ARTICLE",
            article_assembler_service.to_pretty_json(
                {
                    "selected_title": article.get("selected_title") or "",
                    "selected_topic": article.get("selected_topic") or "",
                    "summary": article.get("summary") or "",
                    "content_markdown": (article.get("content_markdown") or "")[:3000],
                }
            ),
            "",
            "REVIEW RULES",
            "- style 和 structure 各自最多 6 个高信号 issue",
            "- audit issues 只列真实风险，不要凑数",
            "- combined_rewrite_suggestions 选最优先的 1-4 条",
        ]

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Output normalisation
    # ------------------------------------------------------------------

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        style = self._normalize_style(data.get("style") or {})
        structure = self._normalize_structure(data.get("structure") or {})
        audit = self._normalize_audit(data.get("audit") or {})

        combined_suggestions_raw = data.get("combined_rewrite_suggestions")
        combined_suggestions = (
            [str(s).strip() for s in combined_suggestions_raw if str(s).strip()][:4]
            if isinstance(combined_suggestions_raw, list)
            else []
        )
        if not combined_suggestions:
            combined_suggestions = list(
                dict.fromkeys(style["rewrite_suggestions"] + structure["rewrite_suggestions"])
            )[:4]

        editorial_passed = bool(data.get("editorial_passed", style["passed"] and structure["passed"] and audit["passed"]))

        return {
            "editorial_passed": editorial_passed,
            "style": style,
            "structure": structure,
            "audit": audit,
            "combined_rewrite_suggestions": combined_suggestions,
        }

    def _normalize_style(self, data: dict[str, Any]) -> dict[str, Any]:
        issues = self._normalize_issues(data.get("issues"), self._STYLE_ISSUE_CODES, "style_drift")
        suggestions = self._normalize_suggestions(data.get("rewrite_suggestions"))
        score = self._clamp_score(data.get("score"), 0.85)
        passed = bool(data.get("passed")) if isinstance(data.get("passed"), bool) else (
            not any(i["severity"] in {"medium", "high"} for i in issues)
        )
        summary = str(data.get("summary") or "").strip() or (
            "Style review passed." if passed else "Style review found voice issues."
        )
        return {
            "reviewer": "style_reviewer",
            "passed": passed,
            "score": score,
            "summary": summary,
            "issues": issues,
            "rewrite_suggestions": suggestions,
        }

    def _normalize_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        issues = self._normalize_issues(data.get("issues"), self._STRUCTURE_ISSUE_CODES, "outline_misaligned")
        suggestions = self._normalize_suggestions(data.get("rewrite_suggestions"))
        score = self._clamp_score(data.get("score"), 0.82)
        passed = bool(data.get("passed")) if isinstance(data.get("passed"), bool) else (
            not any(i["severity"] in {"medium", "high"} for i in issues)
        )
        summary = str(data.get("summary") or "").strip() or (
            "Structure review passed." if passed else "Structure review found layout issues."
        )
        return {
            "reviewer": "structure_reviewer",
            "passed": passed,
            "score": score,
            "summary": summary,
            "issues": issues,
            "rewrite_suggestions": suggestions,
        }

    def _normalize_audit(self, data: dict[str, Any]) -> dict[str, Any]:
        raw_issues = data.get("issues")
        issues: list[dict[str, Any]] = []
        if isinstance(raw_issues, list):
            for item in raw_issues:
                if not isinstance(item, dict):
                    continue
                issue_type = str(item.get("type") or "quality").strip()
                if issue_type not in self._AUDIT_ISSUE_TYPES:
                    issue_type = "quality"
                issues.append(
                    {
                        "type": issue_type,
                        "description": str(item.get("description") or item.get("message") or "").strip(),
                        "severity": self._normalize_severity(item.get("severity")),
                        "location": str(item.get("location") or "").strip() or None,
                    }
                )

        risk_level = str(data.get("risk_level") or "low").strip()
        if risk_level not in {"low", "medium", "high"}:
            severity_set = {i["severity"] for i in issues}
            risk_level = "high" if "high" in severity_set else ("medium" if "medium" in severity_set else "low")

        passed = bool(data.get("passed")) if isinstance(data.get("passed"), bool) else (
            risk_level != "high" and not any(i["severity"] == "high" for i in issues)
        )

        return {
            "passed": passed,
            "risk_level": risk_level,
            "issues": issues,
            "overall_comment": str(data.get("overall_comment") or "").strip() or (
                "内容合规，可发布。" if passed else "存在风险，建议人工复核。"
            ),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_issues(
        self,
        raw: Any,
        allowed_codes: set[str],
        default_code: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        result = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message") or item.get("description") or "").strip()
            if not message:
                continue
            code = str(item.get("code") or "").strip().lower()
            if code not in allowed_codes:
                code = default_code
            result.append(
                {
                    "code": code,
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
        return result

    def _normalize_suggestions(self, raw: Any) -> list[str]:
        if not isinstance(raw, list):
            return []
        return [str(s).strip() for s in raw if str(s).strip()]

    def _clamp_score(self, value: Any, default: float) -> float:
        try:
            if value is not None:
                return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            pass
        return default

    def _normalize_severity(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in {"high", "medium", "low"} else "medium"

    def _as_optional_text(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        style_fallback = {
            "reviewer": "style_reviewer",
            "passed": False,
            "score": None,
            "summary": "Editorial review service degraded. Style audit skipped.",
            "issues": [],
            "rewrite_suggestions": [],
            "failed": True,
            "degraded": True,
        }
        structure_fallback = {
            "reviewer": "structure_reviewer",
            "passed": False,
            "score": None,
            "summary": "Editorial review service degraded. Structure audit skipped.",
            "issues": [],
            "rewrite_suggestions": [],
            "failed": True,
            "degraded": True,
        }
        audit_fallback = {
            "passed": False,
            "risk_level": "medium",
            "issues": [{"type": "system", "description": "审核服务异常，请人工复核", "severity": "medium", "location": None}],
            "overall_comment": "审核服务降级，建议人工复核后发布。",
        }
        return self._success(
            {
                "editorial_passed": False,
                "failed": True,
                "degraded": True,
                "style": style_fallback,
                "structure": structure_fallback,
                "audit": audit_fallback,
                "combined_rewrite_suggestions": [],
            }
        )
