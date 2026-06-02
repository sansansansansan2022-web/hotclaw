"""Reference source digest helpers for article generation prompts."""

from __future__ import annotations

from typing import Any


class ReferenceDigestService:
    """Build compact, deterministic summaries from enabled account references."""

    def build_reference_digest(
        self,
        *,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        limit: int = 3,
    ) -> dict[str, Any]:
        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        sources = [
            source
            for source in account_context.get("reference_sources", [])
            if isinstance(source, dict)
        ]
        preferred_ids = self._preferred_source_ids(ops_context)
        ordered_sources = self._order_sources(sources, preferred_ids)
        selected_sources = ordered_sources[: max(0, limit)]
        source_digests = [self._source_digest(source) for source in selected_sources]

        return {
            "source_count": len(sources),
            "selected_source_ids": [item["id"] for item in source_digests if item.get("id")],
            "preferred_source_names": [item["name"] for item in source_digests if item.get("name")],
            "style_takeaways": self._style_takeaways(source_digests),
            "structure_takeaways": self._structure_takeaways(source_digests),
            "usage_rules": self._usage_rules(source_digests),
            "source_digests": source_digests,
        }

    def _preferred_source_ids(self, ops_context: dict[str, Any]) -> list[str]:
        run_strategy = ops_context.get("run_strategy")
        if not isinstance(run_strategy, dict):
            return []
        raw_ids = run_strategy.get("preferred_reference_source_ids")
        if not isinstance(raw_ids, list):
            return []
        return [str(item).strip() for item in raw_ids if str(item).strip()]

    def _order_sources(
        self,
        sources: list[dict[str, Any]],
        preferred_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not preferred_ids:
            return sources

        indexed_sources = {
            str(source.get("id")).strip(): source
            for source in sources
            if source.get("id") is not None and str(source.get("id")).strip()
        }
        ordered: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for source_id in preferred_ids:
            source = indexed_sources.get(source_id)
            if source is not None:
                ordered.append(source)
                seen_ids.add(source_id)

        for source in sources:
            source_id = str(source.get("id")).strip() if source.get("id") is not None else ""
            if source_id not in seen_ids:
                ordered.append(source)
        return ordered

    def _source_digest(self, source: dict[str, Any]) -> dict[str, Any]:
        name = self._clean_text(source.get("name")) or "Unnamed reference"
        notes = self._clean_text(source.get("notes"))
        preview = (
            self._clean_text(source.get("preview"))
            or self._clean_text(source.get("content_preview"))
            or self._clean_text(source.get("source_value"))
        )
        return {
            "id": self._clean_text(source.get("id")),
            "name": name,
            "source_type": self._clean_text(source.get("source_type")),
            "notes": self._clip_text(notes, 220),
            "preview": self._clip_text(preview, 260),
        }

    def _style_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in source_digests:
            name = source.get("name") or "Reference"
            notes = source.get("notes") or source.get("preview")
            if notes:
                takeaways.append(f"{name}: {notes}")
        return takeaways

    def _structure_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in source_digests:
            name = source.get("name") or "Reference"
            preview = source.get("preview")
            if preview:
                takeaways.append(f"{name} structure cue: {preview}")
        return takeaways

    def _usage_rules(self, source_digests: list[dict[str, Any]]) -> list[str]:
        if not source_digests:
            return [
                "No preferred reference source is available; rely on account positioning and avoid inventing citations."
            ]
        return [
            "Use preferred references for voice, pacing, and structure only.",
            "Do not copy wording, facts, claims, or examples from reference sources unless they are explicitly provided as source material.",
            "Prioritize the selected reference order when reference cues conflict.",
        ]

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())

    def _clip_text(self, value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 1].rstrip() + "..."


reference_digest_service = ReferenceDigestService()
