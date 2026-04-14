"""Scholar paper search skill backed by real academic metadata providers."""

from __future__ import annotations

import asyncio
from typing import Any

from app.skills.adapters.crossref_adapter import crossref_adapter
from app.skills.adapters.openalex_adapter import openalex_adapter
from app.skills.adapters.pubmed_adapter import pubmed_adapter
from app.skills.adapters.scholar_provider_config import provider_includes
from app.skills.adapters.semantic_scholar_adapter import semantic_scholar_adapter
from app.skills.base import BaseSkill
from app.skills.rankers.paper_ranker import paper_ranker
from app.skills.schemas.scholar import ScholarPaperSearchInput
from app.skills.schemas.skill_common import EvidenceItemPayload
from app.core.config import settings
from app.core.exceptions import ConfigError


class ScholarPaperSearchSkill(BaseSkill):
    """Search and curate real paper candidates from academic discovery APIs."""

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
        normalized: list[dict[str, Any]] = []
        normalized_queries = self._build_normalized_queries(payload)
        provider_calls = self._build_provider_calls(payload)
        if not provider_calls:
            raise ConfigError(
                "Scholar skill requires SCHOLAR_PROVIDER to include at least one real source: openalex, semanticscholar, pubmed."
            )

        search_results = await asyncio.gather(
            *provider_calls,
            return_exceptions=True,
        )
        provider_errors: list[Exception] = []
        successful_provider_count = 0
        for result in search_results:
            if isinstance(result, Exception):
                provider_errors.append(result)
                continue
            successful_provider_count += 1
            normalized.extend(result)
        if provider_errors and not normalized and successful_provider_count == 0:
            raise provider_errors[0]

        normalized = await self._enrich_with_crossref(normalized)

        ranked = paper_ranker.rank(topic=payload.topic, papers=normalized, max_results=payload.max_results)
        reading_path = paper_ranker.build_reading_path(ranked)
        evidence_items = [self._to_evidence_item(candidate).model_dump() for candidate in ranked]
        return {
            "status": "success",
            "skill_id": self.skill_id,
            "data": {
                "query": payload.topic,
                "normalized_queries": normalized_queries,
                "results": ranked,
                "summary": self._build_summary(ranked),
                "reading_path": reading_path,
                "evidence_items": evidence_items,
            },
            "error": None,
        }

    def _build_normalized_queries(self, payload: ScholarPaperSearchInput) -> list[str]:
        parts = [payload.topic.strip()]
        parts.extend(item.strip() for item in payload.must_have or [] if item.strip())
        parts.extend(f"-{item.strip()}" for item in payload.exclude_terms or [] if item.strip())
        return [part for part in parts if part]

    def _build_provider_calls(self, payload: ScholarPaperSearchInput) -> list[Any]:
        provider = settings.scholar_provider
        calls: list[Any] = []
        if provider_includes(provider, "openalex"):
            calls.append(self._collect_openalex(payload))
        if provider_includes(provider, "semanticscholar"):
            calls.append(self._collect_semantic_scholar(payload))
        if provider_includes(provider, "pubmed"):
            calls.append(self._collect_pubmed(payload))
        return calls

    async def _collect_openalex(self, payload: ScholarPaperSearchInput) -> list[dict[str, Any]]:
        openalex_payload = await openalex_adapter.search_works(
            topic=payload.topic,
            year_from=payload.year_from,
            year_to=payload.year_to,
            max_results=payload.max_results,
            paper_types=payload.paper_types,
            must_have=payload.must_have,
            exclude_terms=payload.exclude_terms,
        )
        normalized: list[dict[str, Any]] = []
        for item in openalex_payload.get("results") or []:
            if isinstance(item, dict):
                normalized.append(self._normalize_openalex_item(item))
        return normalized

    async def _collect_semantic_scholar(self, payload: ScholarPaperSearchInput) -> list[dict[str, Any]]:
        payload_json = await semantic_scholar_adapter.search_papers(
            topic=payload.topic,
            year_from=payload.year_from,
            year_to=payload.year_to,
            max_results=payload.max_results,
            paper_types=payload.paper_types,
            must_have=payload.must_have,
            exclude_terms=payload.exclude_terms,
        )
        normalized: list[dict[str, Any]] = []
        for item in payload_json.get("data") or []:
            if isinstance(item, dict):
                normalized.append(self._normalize_semantic_scholar_item(item))
        return normalized

    async def _collect_pubmed(self, payload: ScholarPaperSearchInput) -> list[dict[str, Any]]:
        payload_json = await pubmed_adapter.search_papers(
            topic=payload.topic,
            year_from=payload.year_from,
            year_to=payload.year_to,
            max_results=payload.max_results,
            must_have=payload.must_have,
            exclude_terms=payload.exclude_terms,
        )
        normalized: list[dict[str, Any]] = []
        for item in payload_json.get("results") or []:
            if isinstance(item, dict):
                normalized.append(self._normalize_pubmed_item(item))
        return normalized

    async def _enrich_with_crossref(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            crossref_item = await crossref_adapter.enrich_by_title(title)
            enriched.append(self._merge_crossref(item, crossref_item))
        return enriched

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
            "raw_payload_json": {"provider": "openalex", "record": item},
        }

    def _normalize_semantic_scholar_item(self, item: dict[str, Any]) -> dict[str, Any]:
        authors = [
            str(author.get("name") or "").strip()
            for author in (item.get("authors") or [])
            if isinstance(author, dict)
        ]
        external_ids = item.get("externalIds") if isinstance(item.get("externalIds"), dict) else {}
        publication_venue = (
            (item.get("publicationVenue") or {}).get("name")
            if isinstance(item.get("publicationVenue"), dict)
            else None
        )
        publication_types = item.get("publicationTypes") if isinstance(item.get("publicationTypes"), list) else []
        return {
            "title": str(item.get("title") or "").strip(),
            "authors": [name for name in authors if name],
            "year": item.get("year"),
            "venue": publication_venue or item.get("venue"),
            "url": item.get("url"),
            "doi": str(external_ids.get("DOI") or "").strip() or None,
            "abstract_or_summary": str(item.get("abstract") or "").strip() or None,
            "citation_count": int(item.get("citationCount") or 0),
            "paper_type": publication_types[0] if publication_types else None,
            "raw_payload_json": {"provider": "semantic_scholar", "record": item},
        }

    def _normalize_pubmed_item(self, item: dict[str, Any]) -> dict[str, Any]:
        pmid = str(item.get("pmid") or item.get("id") or "").strip()
        doi = str(item.get("doi") or "").strip() or None
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
        if doi:
            url = f"https://doi.org/{doi}"
        return {
            "title": str(item.get("title") or "").strip(),
            "authors": [str(name).strip() for name in (item.get("authors") or []) if str(name).strip()],
            "year": item.get("year"),
            "venue": item.get("venue"),
            "url": url,
            "doi": doi,
            "abstract_or_summary": str(item.get("abstract") or "").strip() or None,
            "citation_count": 0,
            "paper_type": "journal-article",
            "raw_payload_json": {"provider": "pubmed", "record": item},
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
        raw_payload = base.get("raw_payload_json") if isinstance(base.get("raw_payload_json"), dict) else {}
        base["raw_payload_json"] = {
            **raw_payload,
            "crossref": crossref_item,
        }
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
