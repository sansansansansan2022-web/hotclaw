"""Audit agent: reviews content for risks and evidence grounding."""

from __future__ import annotations

import json
import re

import litellm

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings


class AuditAgent(BaseAgent):
    """Review generated content for compliance, quality, and evidence grounding."""

    agent_id = "audit_agent"
    name = "Audit Agent"
    description = "Audit generated content for compliance risks and unsupported evidence claims."

    input_schema = {
        "type": "object",
        "properties": {
            "titles": {"type": "object"},
            "content": {"type": "object"},
            "profile": {"type": "object"},
            "account_context": {"type": "object"},
            "selected_evidence": {"type": "array"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["titles", "content", "profile"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "severity": {"type": "string"},
                        "location": {"type": "string"},
                    },
                },
            },
            "overall_comment": {"type": "string"},
        },
    }

    supported_skills = []

    default_system_prompt = """You are a content audit specialist.

Review the generated article and return strict JSON with:
- passed
- risk_level
- issues
- overall_comment

Rules:
- Flag unsupported paper titles or repository names that do not exist in the evidence list.
- Flag claims like 顶会, 顶刊, 高水平, 爆火, state-of-the-art, best, first if the evidence does not support them.
- Balance compliance and readability, but do not let unsupported claims pass.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile", {})
        titles_data = input_data.get("titles", {})
        content_data = input_data.get("content", {})
        selected_evidence = input_data.get("selected_evidence") or []
        citation_guardrails = input_data.get("citation_guardrails") or {}
        system_prompt = context.get("system_prompt") or self.default_system_prompt
        user_prompt = self._build_user_prompt(
            profile=profile,
            titles_data=titles_data,
            content_data=content_data,
            selected_evidence=selected_evidence,
            citation_guardrails=citation_guardrails,
        )

        heuristic_issues = self._detect_grounding_issues(content_data, selected_evidence)

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
            issues = data.get("issues") if isinstance(data.get("issues"), list) else []
            issues.extend(heuristic_issues)
            data["issues"] = issues
            data["risk_level"] = self._derive_risk_level(issues)
            data["passed"] = not any(issue.get("severity") == "high" for issue in issues)
            if heuristic_issues:
                prefix = "Heuristic grounding checks found additional evidence issues. "
                data["overall_comment"] = prefix + str(data.get("overall_comment") or "").strip()
            return self._success(data)

        except json.JSONDecodeError as exc:
            return self._success(self._fallback_audit(heuristic_issues, f"Failed to parse audit JSON: {exc}"))
        except Exception as exc:
            return self._success(self._fallback_audit(heuristic_issues, str(exc)))

    def _build_user_prompt(
        self,
        *,
        profile: dict,
        titles_data: dict,
        content_data: dict,
        selected_evidence: list[dict],
        citation_guardrails: dict[str, bool],
    ) -> str:
        tone = profile.get("tone", "neutral")
        domain = profile.get("domain", "unknown")
        title_list = titles_data.get("titles", []) if isinstance(titles_data, dict) else []
        content_md = content_data.get("content_markdown", "") if isinstance(content_data, dict) else ""

        content_preview = content_md[:5000] + "..." if len(content_md) > 5000 else content_md
        prompt_parts = [
            "Audit the following article.",
            "",
            "ACCOUNT",
            json.dumps({"domain": domain, "tone": tone}, ensure_ascii=False, indent=2),
            "",
            "TITLE CANDIDATES",
            json.dumps(title_list[:4], ensure_ascii=False, indent=2),
            "",
            "SELECTED EVIDENCE",
            json.dumps(selected_evidence[:12], ensure_ascii=False, indent=2),
            "",
            "CITATION GUARDRAILS",
            json.dumps(citation_guardrails, ensure_ascii=False, indent=2),
            "",
            "ARTICLE",
            content_preview,
            "",
            "REQUIREMENTS",
            "- Output strict JSON only.",
            "- Check compliance, exaggeration, tone fit, and unsupported evidence claims.",
        ]
        return "\n".join(prompt_parts)

    def _detect_grounding_issues(self, content_data: dict, selected_evidence: list[dict]) -> list[dict]:
        content_md = str((content_data or {}).get("content_markdown") or "")
        evidence_titles = {
            self._normalize_name(item.get("title"))
            for item in selected_evidence
            if isinstance(item, dict) and self._normalize_name(item.get("title"))
        }
        evidence_repo_names = {
            self._normalize_name(item.get("source_id"))
            for item in selected_evidence
            if isinstance(item, dict)
            and str(item.get("source_type") or "").startswith("github")
            and self._normalize_name(item.get("source_id"))
        }

        issues: list[dict] = []
        repo_mentions = {
            self._normalize_name(match)
            for match in re.findall(r"\b[\w.-]+/[\w.-]+\b", content_md)
            if self._normalize_name(match)
        }
        for repo_name in sorted(repo_mentions):
            if repo_name not in evidence_repo_names:
                issues.append(
                    {
                        "type": "unsupported_repo_reference",
                        "description": f"Repository name '{repo_name}' does not appear in selected evidence.",
                        "severity": "medium",
                        "location": "content",
                    }
                )

        title_mentions = {
            self._normalize_name(match)
            for match in re.findall(r"[《“\"]([^》”\"]{8,120})[》”\"]", content_md)
            if self._normalize_name(match)
        }
        for title in sorted(title_mentions):
            if title not in evidence_titles and "/" not in title:
                issues.append(
                    {
                        "type": "unsupported_paper_reference",
                        "description": f"Quoted title '{title}' does not appear in selected evidence.",
                        "severity": "medium",
                        "location": "content",
                    }
                )

        if re.search(r"顶会|顶刊|高水平|爆火|state[- ]of[- ]the[- ]art|SOTA|最强|第一", content_md, re.IGNORECASE):
            strong_authority = any(
                isinstance(item, dict) and float(item.get("authority_score") or 0.0) >= 0.85
                for item in selected_evidence
            )
            if not strong_authority:
                issues.append(
                    {
                        "type": "unsupported_hype_claim",
                        "description": "The article uses strong authority or hype claims without strong evidence support.",
                        "severity": "medium",
                        "location": "content",
                    }
                )
        return issues

    def _fallback_audit(self, heuristic_issues: list[dict], error_message: str) -> dict:
        issues = list(heuristic_issues)
        if error_message:
            issues.append(
                {
                    "type": "audit_runtime_error",
                    "description": f"Audit model failed: {error_message}",
                    "severity": "medium",
                    "location": "system",
                }
            )
        risk_level = self._derive_risk_level(issues)
        return {
            "passed": not any(issue.get("severity") == "high" for issue in issues),
            "risk_level": risk_level,
            "issues": issues,
            "overall_comment": "Audit fell back to deterministic grounding checks.",
        }

    def _derive_risk_level(self, issues: list[dict]) -> str:
        severities = {str(item.get("severity") or "").lower() for item in issues if isinstance(item, dict)}
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"

    def _normalize_name(self, value: object) -> str:
        raw = str(value or "").strip().lower()
        return re.sub(r"\s+", " ", raw)

    def _parse_json(self, content: str) -> dict:
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        heuristic_issues = self._detect_grounding_issues(
            input_data.get("content") or {},
            input_data.get("selected_evidence") or [],
        )
        return self._success(self._fallback_audit(heuristic_issues, str(error)))
