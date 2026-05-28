"""Reference source digest helpers for content generation prompts."""

from __future__ import annotations

from typing import Any


class ReferenceDigestService:
    """Build compact, deterministic summaries from account reference sources."""

    def build_reference_digest(
        self,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        *,
        limit: int = 3,
    ) -> dict[str, Any]:
        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        run_strategy = ops_context.get("run_strategy") if isinstance(ops_context.get("run_strategy"), dict) else {}

        sources = self._normalize_reference_sources(account_context.get("reference_sources"))
        preferred_ids = self._normalize_string_list(run_strategy.get("preferred_reference_source_ids"))
        selected_sources = self._prioritize_reference_sources(sources, preferred_ids, limit=limit)

        return {
            "source_count": len(sources),
            "selected_source_ids": [item["id"] for item in selected_sources if item.get("id")],
            "preferred_source_names": [item["name"] for item in selected_sources if item.get("name")],
            "style_takeaways": self._build_style_takeaways(selected_sources),
            "structure_takeaways": self._build_structure_takeaways(selected_sources),
            "usage_rules": self._build_usage_rules(selected_sources),
            "source_digests": [self._source_digest(item) for item in selected_sources],
        }

    def _build_style_takeaways(self, sources: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in sources:
            clues = source.get("style_clues") or source.get("notes") or source.get("preview")
            if clues:
                takeaways.append(f"{source['name']}: {self._clip_text(clues, 160)}")
        return takeaways[:6]

    def _build_structure_takeaways(self, sources: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in sources:
            preview = source.get("preview")
            if preview:
                takeaways.append(f"Use {source['name']} as a structure reference: {self._clip_text(preview, 180)}")
        return takeaways[:6]

    def _build_usage_rules(self, sources: list[dict[str, Any]]) -> list[str]:
        if not sources:
            return []
        return [
            "Use reference sources for tone, pacing, and structure only.",
            "Do not copy distinctive sentences or claims from the reference material.",
            "Prefer the selected reference order when resolving style conflicts.",
        ]

    def _source_digest(self, source: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": source.get("id"),
            "name": source.get("name"),
            "source_type": source.get("source_type"),
            "sync_status": source.get("sync_status"),
            "article_count": source.get("article_count"),
            "resolved_title": source.get("resolved_title"),
            "notes": source.get("notes"),
            "preview": source.get("preview"),
            "style_clues": source.get("style_clues"),
        }

    def _normalize_reference_sources(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata_json") if isinstance(item.get("metadata_json"), dict) else {}
            preview = self._clean_text(item.get("preview") or metadata.get("preview"))
            source_value = self._clean_text(item.get("source_value"))
            if not preview and source_value:
                preview = source_value

            notes = self._clip_text(item.get("notes"), 220)
            normalized.append(
                {
                    "id": self._clean_text(item.get("id")),
                    "name": self._clean_text(item.get("name")) or "Unnamed reference",
                    "source_type": self._clean_text(item.get("source_type")) or "reference",
                    "sync_status": self._clean_text(item.get("sync_status")) or "unknown",
                    "article_count": int(item.get("article_count") or 0),
                    "resolved_title": self._clip_text(item.get("resolved_title") or metadata.get("resolved_title"), 120),
                    "notes": notes,
                    "preview": self._clip_text(preview, 260),
                    "style_clues": self._clip_text(item.get("style_clues") or notes, 180),
                }
            )
        return normalized

    def _prioritize_reference_sources(
        self,
        sources: list[dict[str, Any]],
        preferred_ids: list[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if not sources:
            return []

        preferred_index = {source_id: index for index, source_id in enumerate(preferred_ids)}

        def _sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
            item_id = self._clean_text(item.get("id"))
            is_preferred = 0 if item_id in preferred_index else 1
            preferred_order = preferred_index.get(item_id, 999)
            return (is_preferred, preferred_order, self._clean_text(item.get("name")))

        return sorted(sources, key=_sort_key)[:limit]

    def _normalize_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = self._clean_text(item)
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    def _clip_text(self, value: Any, limit: int) -> str:
        text = self._clean_text(value)
        if len(text) <= limit:
            return text
        clipped = text[: max(limit - 3, 0)].rstrip()
        return f"{clipped}..."

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


reference_digest_service = ReferenceDigestService()
