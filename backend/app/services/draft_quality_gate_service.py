"""Draft quality gate adapters for pre-publish and post-process control."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.models.tables import ArticleDraftModel, AuditResultModel
from app.services.article_assembler_service import article_assembler_service

logger = get_logger(__name__)


class DraftQualityGateService:
    """Evaluate draft quality with a pluggable adapter and persist audit records."""

    RESULT_KEY = "draft_quality_gate"
    STATUS_PASSED = "passed"
    STATUS_BLOCKED = "blocked"
    STATUS_SKIPPED = "skipped"

    async def ensure_gate_result(
        self,
        result_data: dict[str, Any],
        *,
        task_id: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        existing = result_data.get(self.RESULT_KEY)
        if isinstance(existing, dict) and "passed" in existing:
            return self.normalize_gate_result(existing)

        gate_result = await self.evaluate_result(
            result_data,
            task_id=task_id,
            account_id=account_id,
        )
        result_data[self.RESULT_KEY] = gate_result
        return gate_result

    async def evaluate_result(
        self,
        result_data: dict[str, Any],
        *,
        task_id: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        if not settings.draft_quality_gate_enabled:
            return self._build_result(
                passed=True,
                status=self.STATUS_SKIPPED,
                provider="disabled",
                risk_level="low",
                score=1.0,
                issues=[],
                failure_reasons=[],
                summary="Draft quality gate is disabled.",
                raw_response=None,
            )

        provider = (settings.draft_quality_gate_provider or "internal").strip().lower()
        try:
            if provider == "zhuque":
                return await self._evaluate_with_zhuque(
                    result_data,
                    task_id=task_id,
                    account_id=account_id,
                )
            return self._evaluate_internal(result_data, provider=provider)
        except Exception as exc:
            logger.warning(
                "draft_quality_gate_provider_failed",
                provider=provider,
                task_id=task_id,
                account_id=account_id,
                error=str(exc),
            )
            if settings.draft_quality_gate_fail_closed:
                return self._build_result(
                    passed=False,
                    status=self.STATUS_BLOCKED,
                    provider=provider,
                    risk_level="high",
                    score=0.0,
                    issues=[
                        {
                            "code": "quality_gate_provider_failed",
                            "severity": "high",
                            "message": str(exc),
                            "location": "draft_quality_gate",
                        }
                    ],
                    failure_reasons=["quality_gate_provider_failed"],
                    summary="Draft quality gate provider failed; blocking because fail-closed is enabled.",
                    raw_response=None,
                )
            return self._evaluate_internal(result_data, provider="internal_fallback")

    def normalize_gate_result(self, value: dict[str, Any]) -> dict[str, Any]:
        score = self._to_float(value.get("score"))
        if score is None:
            score = 1.0 if value.get("passed") else 0.0
        issues = self._normalize_issues(value.get("issues"))
        failure_reasons = self._normalize_string_list(value.get("failure_reasons"))
        passed = bool(value.get("passed"))
        risk_level = self._normalize_risk(value.get("risk_level"), issues, passed=passed)
        status = str(value.get("status") or (self.STATUS_PASSED if passed else self.STATUS_BLOCKED))
        return self._build_result(
            passed=passed,
            status=status,
            provider=str(value.get("provider") or "unknown"),
            risk_level=risk_level,
            score=score,
            issues=issues,
            failure_reasons=failure_reasons,
            summary=str(value.get("summary") or value.get("overall_comment") or "").strip(),
            raw_response=value.get("raw_response"),
        )

    async def persist_for_draft(
        self,
        *,
        draft: ArticleDraftModel,
        result_data: dict[str, Any],
        db: AsyncSession,
    ) -> dict[str, Any]:
        gate_result = await self.ensure_gate_result(
            result_data,
            task_id=draft.task_id,
            account_id=draft.account_id,
        )
        await self._upsert_audit_record(draft=draft, gate_result=gate_result, db=db)
        if not gate_result["passed"]:
            draft.draft_status = "draft"
            draft.publish_review_required = True
            draft.confirmed_at = None
            draft.confirmed_by = None
            logger.warning(
                "draft_quality_gate_blocked",
                draft_id=draft.id,
                task_id=draft.task_id,
                account_id=draft.account_id,
                risk_level=gate_result["risk_level"],
                failure_reasons=gate_result["failure_reasons"],
            )
        db.add(draft)
        await db.flush()
        return gate_result

    async def _evaluate_with_zhuque(
        self,
        result_data: dict[str, Any],
        *,
        task_id: str | None,
        account_id: str | None,
    ) -> dict[str, Any]:
        endpoint = settings.zhuque_ai_check_endpoint.strip()
        api_key = settings.zhuque_ai_check_api_key.strip()
        if not endpoint or not api_key:
            raise ValueError("Zhuque AI check endpoint or API key is not configured")

        article = article_assembler_service.extract_article_payload(result_data)
        payload = {
            "task_id": task_id,
            "account_id": account_id,
            "title": article.get("selected_title"),
            "summary": article.get("summary"),
            "content_markdown": article.get("content_markdown"),
            "content_html": article.get("content_html"),
            "metadata": {
                "selected_topic": article.get("selected_topic"),
                "word_count": article.get("word_count"),
                "tags": article.get("tags"),
            },
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(float(settings.draft_quality_gate_timeout_seconds), connect=8.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return self._normalize_provider_response(data, provider="zhuque")

    def _evaluate_internal(self, result_data: dict[str, Any], *, provider: str) -> dict[str, Any]:
        audit_result = result_data.get("audit_result")
        if isinstance(audit_result, dict) and ("passed" in audit_result or "risk_level" in audit_result):
            return self._from_audit_result(audit_result, provider=provider)

        article = article_assembler_service.extract_article_payload(result_data)
        content = str(article.get("content_markdown") or "").strip()
        issues: list[dict[str, Any]] = []
        if not content:
            issues.append(
                {
                    "code": "empty_draft",
                    "severity": "high",
                    "message": "Generated draft content is empty.",
                    "location": "content_markdown",
                }
            )
        if content and article_assembler_service.count_words(content) < 120:
            issues.append(
                {
                    "code": "thin_draft",
                    "severity": "medium",
                    "message": "Draft is unusually short; keep it out of auto post-processing/publishing until reviewed.",
                    "location": "content_markdown",
                }
            )
        high_issue = any(str(item.get("severity")) == "high" for item in issues)
        passed = not high_issue
        risk_level = "high" if high_issue else ("medium" if issues else "low")
        score = 1.0 if not issues else (0.62 if passed else 0.0)
        failure_reasons = [str(item.get("code")) for item in issues if str(item.get("code")).strip()]
        return self._build_result(
            passed=passed,
            status=self.STATUS_PASSED if passed else self.STATUS_BLOCKED,
            provider=provider,
            risk_level=risk_level,
            score=score,
            issues=issues,
            failure_reasons=[] if passed else failure_reasons,
            summary=(
                "Internal draft quality gate passed."
                if passed
                else "Internal draft quality gate blocked the draft before post-processing."
            ),
            raw_response=None,
        )

    def _from_audit_result(self, audit_result: dict[str, Any], *, provider: str) -> dict[str, Any]:
        issues = self._normalize_issues(audit_result.get("issues"))
        risk_level = self._normalize_risk(audit_result.get("risk_level"), issues, passed=bool(audit_result.get("passed")))
        score = self._to_float(audit_result.get("score"))
        if score is None:
            score = 0.92 if risk_level == "low" else (0.55 if risk_level == "medium" else 0.0)
        passed = bool(audit_result.get("passed")) and risk_level != "high" and score >= settings.draft_quality_gate_min_score
        failure_reasons = [] if passed else self._failure_reasons_from_issues(issues, fallback=f"audit_{risk_level}_risk")
        return self._build_result(
            passed=passed,
            status=self.STATUS_PASSED if passed else self.STATUS_BLOCKED,
            provider=provider,
            risk_level=risk_level,
            score=score,
            issues=issues,
            failure_reasons=failure_reasons,
            summary=str(audit_result.get("overall_comment") or audit_result.get("summary") or "").strip()
            or ("Audit-backed gate passed." if passed else "Audit-backed gate blocked the draft."),
            raw_response=audit_result,
        )

    def _normalize_provider_response(self, data: Any, *, provider: str) -> dict[str, Any]:
        response = data if isinstance(data, dict) else {}
        issues = self._normalize_issues(response.get("issues") or response.get("problems") or response.get("reasons"))
        raw_passed = response.get("passed")
        if raw_passed is None:
            raw_passed = response.get("pass")
        score = self._to_float(response.get("score") or response.get("quality_score") or response.get("confidence"))
        risk_level = self._normalize_risk(response.get("risk_level") or response.get("risk"), issues, passed=bool(raw_passed))
        if score is None:
            score = 0.92 if risk_level == "low" else (0.55 if risk_level == "medium" else 0.0)
        passed = bool(raw_passed) and risk_level != "high" and score >= settings.draft_quality_gate_min_score
        failure_reasons = [] if passed else self._failure_reasons_from_issues(issues, fallback=f"{provider}_gate_blocked")
        return self._build_result(
            passed=passed,
            status=self.STATUS_PASSED if passed else self.STATUS_BLOCKED,
            provider=provider,
            risk_level=risk_level,
            score=score,
            issues=issues,
            failure_reasons=failure_reasons,
            summary=str(response.get("summary") or response.get("overall_comment") or response.get("message") or "").strip()
            or (f"{provider} gate passed." if passed else f"{provider} gate blocked the draft."),
            raw_response=response,
        )

    async def _upsert_audit_record(
        self,
        *,
        draft: ArticleDraftModel,
        gate_result: dict[str, Any],
        db: AsyncSession,
    ) -> None:
        result = await db.execute(select(AuditResultModel).where(AuditResultModel.draft_id == draft.id))
        audit = result.scalar_one_or_none()
        if audit is None:
            audit = AuditResultModel(task_id=draft.task_id, draft_id=draft.id)
        audit.passed = bool(gate_result["passed"])
        audit.risk_level = str(gate_result["risk_level"] or "low")
        audit.issues = gate_result.get("issues") or []
        audit.overall_comment = str(gate_result.get("summary") or "")
        audit.updated_at = datetime.now(timezone.utc)
        db.add(audit)
        await db.flush()

    def _build_result(
        self,
        *,
        passed: bool,
        status: str,
        provider: str,
        risk_level: str,
        score: float,
        issues: list[dict[str, Any]],
        failure_reasons: list[str],
        summary: str,
        raw_response: Any,
    ) -> dict[str, Any]:
        return {
            "passed": bool(passed),
            "status": status,
            "provider": provider,
            "risk_level": risk_level,
            "score": round(max(0.0, min(float(score), 1.0)), 4),
            "threshold": settings.draft_quality_gate_min_score,
            "issues": issues,
            "failure_reasons": failure_reasons,
            "summary": summary,
            "raw_response": raw_response,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def _normalize_issues(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        issues: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                code = str(item.get("code") or item.get("type") or item.get("reason_code") or "quality_issue").strip()
                severity = str(item.get("severity") or item.get("level") or "medium").strip().lower()
                message = str(item.get("message") or item.get("description") or item.get("reason") or "").strip()
                location = str(item.get("location") or item.get("field") or "content").strip()
            else:
                code = "quality_issue"
                severity = "medium"
                message = str(item).strip()
                location = "content"
            if severity not in {"low", "medium", "high"}:
                severity = "medium"
            issues.append({"code": code, "severity": severity, "message": message, "location": location})
        return issues

    def _failure_reasons_from_issues(self, issues: list[dict[str, Any]], *, fallback: str) -> list[str]:
        reasons = [
            str(item.get("code")).strip()
            for item in issues
            if str(item.get("code") or "").strip()
        ]
        return reasons or [fallback]

    def _normalize_risk(self, value: Any, issues: list[dict[str, Any]], *, passed: bool) -> str:
        risk = str(value or "").strip().lower()
        if risk in {"low", "medium", "high"}:
            return risk
        if any(item.get("severity") == "high" for item in issues):
            return "high"
        if any(item.get("severity") == "medium" for item in issues):
            return "medium"
        return "low" if passed else "high"

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _to_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


draft_quality_gate_service = DraftQualityGateService()
