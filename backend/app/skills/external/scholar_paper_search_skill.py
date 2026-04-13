"""Scholar paper search skill backed by OpenAlex and Crossref."""

from __future__ import annotations

from typing import Any

from app.skills.adapters.crossref_adapter import crossref_adapter
from app.skills.adapters.openalex_adapter import openalex_adapter
from app.skills.base import BaseSkill
from app.skills.rankers.paper_ranker import paper_ranker
from app.skills.schemas.scholar import ScholarPaperSearchInput
from app.skills.schemas.skill_common import EvidenceItemPayload


class ScholarPaperSearchSkill(BaseSkill):
    """Search and curate real paper candidates from OpenAlex plus Crossref."""

    skill_id = "scholar_paper_search_skill"
    name = "Scholar Paper Search Skill"
    description = "Searches OpenAlex and enriches metadata with Crossref for paper-based evidence."

    input_schema = ScholarPaperSearchInput.model_json_schema()
    output_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "normalized_queries": {"type": "array", "items": {"type": "string"}},
            "results": {"type": "array"},
            "summary": {"type": "string"},
            "reading_path": {"type": "array"},
            "evidence_items": {"type": "array"},
        },
    }

    async def execute(self, input_data: dict) -> dict:
        payload = ScholarPaperSearchInput(**input_data)
        openalex_payload = await openalex_adapter.search_works(
            topic=payload.topic,
            year_from=payload.year_from,
            year_to=payload.year_to,
            max_results=payload.max_results,
            paper_types=payload.paper_types,
            must_have=payload.must_have,
            exclude_terms=payload.exclude_terms,
        )
        raw_results = openalex_payload.get("results") or []
        normalized: list[dict[str, Any]] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            normalized_item = self._normalize_openalex_item(item)
            crossref_item = await crossref_adapter.enrich_by_title(normalized_item["title"])
            normalized.append(self._merge_crossref(normalized_item, crossref_item))

        ranked = paper_ranker.rank(topic=payload.topic, papers=normalized, max_results=payload.max_results)
        reading_path = paper_ranker.build_reading_path(ranked)
        evidence_items = [self._to_evidence_item(candidate).model_dump() for candidate in ranked]
        return {
            "status": "success",
            "skill_id": self.skill_id,
            "data": {
                "query": payload.topic,
                "normalized_queries": [payload.topic],
                "results": ranked,
                "summary": self._build_summary(ranked),
                "reading_path": reading_path,
                "evidence_items": evidence_items,
            },
            "error": None,
        }

    def _normalize_openalex_item(self, item: dict[str, Any]) -> dict[str, Any]:
        authors = [
            str(((authorship.get("author") or {}) if isinstance(authorship, dict) else {}).get("display_name") or "").strip()
            for authorship in item.get("authorships") or []
            if isinstance(authorship, dict)
        ]
        venue = (
            ((item.get("primary_location") or {}).get("source") or {}).get("display_name")
            if isinstance(item.get("primary_location"), dict)
            else None
        )
        abstract = ""
        abstract_index = item.get("abstract_inverted_index")
        if isinstance(abstract_index, dict):
            rebuilt: dict[int, str] = {}
            for token, positions in abstract_index.items():
                for position in positions if isinstance(positions, list) else []:
                    rebuilt[int(position)] = token
            abstract = " ".join(rebuilt[key] for key in sorted(rebuilt))
        return {
            "title": str(item.get("display_name") or "").strip(),
            "authors": [name for name in authors if name],
            "year": item.get("publication_year"),
            "venue": venue,
            "url": item.get("id"),
            "doi": str(item.get("doi") or "").replace("https://doi.org/", "").strip() or None,
            "abstract_or_summary": abstract[:2000] if abstract else None,
            "citation_count": int(item.get("cited_by_count") or 0),
            "paper_type": item.get("type"),
            "raw_payload_json": item,
        }

    def _merge_crossref(self, base: dict[str, Any], crossref_item: dict[str, Any] | None) -> dict[str, Any]:
        if not crossref_item:
            return base
        title = " ".join(crossref_item.get("title") or []).strip()
        venue = " ".join(crossref_item.get("container-title") or []).strip()
        if title and len(title) >= len(base.get("title") or ""):
            base["title"] = title
        if venue:
            base["venue"] = venue
        if crossref_item.get("DOI"):
            base["doi"] = crossref_item.get("DOI")
        if crossref_item.get("URL"):
            base["url"] = crossref_item.get("URL")
        if not base.get("citation_count"):
            base["citation_count"] = int(crossref_item.get("is-referenced-by-count") or 0)
        return base

    def _to_evidence_item(self, candidate: dict[str, Any]) -> EvidenceItemPayload:
        score = candidate.get("score_breakdown") or {}
        return EvidenceItemPayload(
            source_type="scholar_paper",
            source_id=candidate.get("doi") or candidate.get("url") or candidate.get("title"),
            title=candidate.get("title") or "",
            url=candidate.get("url"),
            summary=candidate.get("abstract_or_summary") or candidate.get("why_selected") or "",
            raw_payload_json=candidate.get("raw_payload_json") or candidate,
            normalized_payload_json=candidate,
            relevance_score=float(score.get("relevance") or 0.0),
            authority_score=float(score.get("venue_quality") or 0.0),
            freshness_score=float(score.get("freshness") or 0.0),
            practical_score=float(score.get("reproducibility_signal") or 0.0),
            selected_reason=str(candidate.get("why_selected") or ""),
            risk_flags=candidate.get("risk_flags") or [],
        )

    def _build_summary(self, ranked: list[dict[str, Any]]) -> str:
        if not ranked:
            return "No papers matched the current topic."
        titles = "; ".join(item["title"] for item in ranked[:3])
        return f"Scholar curation selected {len(ranked)} paper candidates. Strongest signals: {titles}."
