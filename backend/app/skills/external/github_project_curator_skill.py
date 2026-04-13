"""GitHub project curator skill with real REST API backing."""

from __future__ import annotations

from typing import Any

from app.skills.adapters.github_search_adapter import github_search_adapter
from app.skills.base import BaseSkill
from app.skills.rankers.repo_ranker import repo_ranker
from app.skills.schemas.github import GitHubProjectCuratorInput
from app.skills.schemas.skill_common import EvidenceItemPayload


class GitHubProjectCuratorSkill(BaseSkill):
    """Curate real GitHub repositories for technical topic discovery."""

    skill_id = "github_project_curator_skill"
    name = "GitHub Project Curator Skill"
    description = "Searches GitHub and curates project candidates with multi-signal ranking."

    input_schema = GitHubProjectCuratorInput.model_json_schema()
    output_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "normalized_queries": {"type": "array", "items": {"type": "string"}},
            "results": {"type": "array"},
            "summary": {"type": "string"},
            "buckets": {"type": "object"},
            "evidence_items": {"type": "array"},
        },
    }

    async def execute(self, input_data: dict) -> dict:
        payload = GitHubProjectCuratorInput(**input_data)
        search_payload = await github_search_adapter.search_repositories(
            topic=payload.topic,
            time_window=payload.time_window,
            language_filters=payload.language_filters,
            max_results=payload.max_results,
            exclude_terms=payload.exclude_terms,
            require_license=payload.require_license,
            prefer_active=payload.prefer_active,
            categories=payload.categories,
        )
        items = search_payload.get("items") or []
        enriched: list[dict[str, Any]] = []
        for item in items[: min(len(items), payload.max_results * 3)]:
            full_name = str(item.get("full_name") or "").strip()
            readme_text = await github_search_adapter.fetch_readme(full_name) if full_name else None
            enriched.append({**item, "_readme_text": readme_text or ""})

        ranked, buckets = repo_ranker.rank(
            topic=payload.topic,
            repos=enriched,
            max_results=payload.max_results,
        )
        evidence_items = [self._to_evidence_item(candidate).model_dump() for candidate in ranked]
        return {
            "status": "success",
            "skill_id": self.skill_id,
            "data": {
                "query": search_payload.get("query") or payload.topic,
                "normalized_queries": [search_payload.get("query") or payload.topic],
                "results": ranked,
                "summary": self._build_summary(ranked),
                "buckets": buckets,
                "evidence_items": evidence_items,
            },
            "error": None,
        }

    def _to_evidence_item(self, candidate: dict[str, Any]) -> EvidenceItemPayload:
        score = candidate.get("score_breakdown") or {}
        return EvidenceItemPayload(
            source_type="github_repo",
            source_id=candidate.get("full_name"),
            title=candidate.get("full_name") or candidate.get("repo_name") or "",
            url=candidate.get("url"),
            summary=candidate.get("description") or candidate.get("why_selected") or "",
            raw_payload_json=candidate,
            normalized_payload_json=candidate,
            relevance_score=float(score.get("topic_relevance") or 0.0),
            authority_score=float(score.get("engineering_quality") or 0.0),
            freshness_score=float(score.get("maintenance") or 0.0),
            practical_score=float(score.get("docs_quality") or 0.0),
            selected_reason=str(candidate.get("why_selected") or ""),
            risk_flags=candidate.get("risk_flags") or [],
        )

    def _build_summary(self, ranked: list[dict[str, Any]]) -> str:
        if not ranked:
            return "No GitHub repositories matched the current topic."
        names = ", ".join(item["full_name"] for item in ranked[:3])
        return f"GitHub curation selected {len(ranked)} repository candidates. Strongest signals: {names}."
