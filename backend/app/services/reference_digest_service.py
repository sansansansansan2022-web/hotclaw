"""Reference source digest helpers for content-generation prompts."""

from __future__ import annotations

from typing import Any


class ReferenceDigestService:
    """Build compact, deterministic briefs from account reference sources."""

    def build_reference_digest(
        self,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        *,
        limit: int = 3,
    ) -> dict[str, Any]:
        sources = self._normalize_reference_sources(account_context)
        preferred_ids = self._preferred_source_ids(ops_context)
        prioritized = self._prioritize_sources(sources, preferred_ids)
        selected = prioritized[: max(limit, 0)]

        return {
            "source_count": len(sources),
            "selected_source_ids": [source["id"] for source in selected],
            "preferred_source_names": [source["name"] for source in selected if source["id"] in preferred_ids]
            or [source["name"] for source in selected],
            "style_takeaways": self._style_takeaways(selected),
            "structure_takeaways": self._structure_takeaways(selected),
            "usage_rules": self._usage_rules(selected, preferred_ids),
            "source_digests": [self._source_digest(source) for source in selected],
        }

    def _normalize_reference_sources(self, account_context: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(account_context, dict):
            return []

        raw_sources = account_context.get("reference_sources")
        if not isinstance(raw_sources, list):
            return []

        normalized: list[dict[str, Any]] = []
        for index, raw_source in enumerate(raw_sources):
            if not isinstance(raw_source, dict):
                continue

            source_id = self._clean_text(raw_source.get("id")) or str(index + 1)
            name = self._clean_text(raw_source.get("name")) or f"Reference Source {index + 1}"
            notes = self._clean_text(raw_source.get("notes"))
            preview = self._clean_text(raw_source.get("preview"))
            resolved_title = self._clean_text(raw_source.get("resolved_title"))
            metadata = raw_source.get("metadata_json") if isinstance(raw_source.get("metadata_json"), dict) else {}
            if not preview:
                preview = self._clean_text(metadata.get("preview"))
            if not resolved_title:
                resolved_title = self._clean_text(metadata.get("resolved_title"))

            normalized.append(
                {
                    "id": source_id,
                    "name": name,
                    "source_type": self._clean_text(raw_source.get("source_type")),
                    "sync_status": self._clean_text(raw_source.get("sync_status")),
                    "article_count": int(raw_source.get("article_count") or 0),
                    "notes": self._clip_text(notes, 260),
                    "preview": self._clip_text(preview, 320),
                    "resolved_title": resolved_title,
                    "original_index": index,
                }
            )

        return normalized

    def _preferred_source_ids(self, ops_context: dict[str, Any] | None) -> list[str]:
        if not isinstance(ops_context, dict):
            return []

        run_strategy = ops_context.get("run_strategy")
        if not isinstance(run_strategy, dict):
            return []

        raw_ids = run_strategy.get("preferred_reference_source_ids")
        if not isinstance(raw_ids, list):
            return []

        preferred_ids: list[str] = []
        seen: set[str] = set()
        for raw_id in raw_ids:
            source_id = self._clean_text(raw_id)
            if source_id and source_id not in seen:
                preferred_ids.append(source_id)
                seen.add(source_id)
        return preferred_ids

    def _prioritize_sources(
        self, sources: list[dict[str, Any]], preferred_ids: list[str]
    ) -> list[dict[str, Any]]:
        preferred_order = {source_id: index for index, source_id in enumerate(preferred_ids)}

        def sort_key(source: dict[str, Any]) -> tuple[int, int, int]:
            source_id = source["id"]
            preferred_rank = preferred_order.get(source_id)
            status_rank = 0 if source.get("sync_status") in {"synced", "manual_only"} else 1
            if preferred_rank is not None:
                return (0, preferred_rank, int(source["original_index"]))
            return (1, status_rank, int(source["original_index"]))

        return sorted(sources, key=sort_key)

    def _style_takeaways(self, sources: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in sources:
            basis = source.get("notes") or source.get("preview") or source.get("resolved_title")
            if basis:
                takeaways.append(f"{source['name']}: {basis}")
        return takeaways[:5]

    def _structure_takeaways(self, sources: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in sources:
            preview = source.get("preview")
            if preview:
                takeaways.append(f"Use {source['name']} as structural reference: {preview}")
        return takeaways[:5]

    def _usage_rules(self, sources: list[dict[str, Any]], preferred_ids: list[str]) -> list[str]:
        if not sources:
            return []

        rules = [
            "Use reference sources as style and structure guidance; do not copy their wording.",
            "Preserve the current account positioning and selected topic over reference-source phrasing.",
        ]
        if preferred_ids:
            rules.append("Prioritize operator-selected preferred reference sources when style cues conflict.")
        return rules

    def _source_digest(self, source: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": source["id"],
            "name": source["name"],
            "source_type": source.get("source_type"),
            "sync_status": source.get("sync_status"),
            "notes": source.get("notes"),
            "preview": source.get("preview"),
            "resolved_title": source.get("resolved_title"),
        }

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())

    def _clip_text(self, value: Any, max_chars: int) -> str:
        text = self._clean_text(value)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + "..."


reference_digest_service = ReferenceDigestService()
