"""Reference source digest helpers for account-aware content prompts."""

from __future__ import annotations

from typing import Any


class ReferenceDigestService:
    """Build compact, stable reference-source summaries for content agents."""

    _USAGE_RULES = [
        "Borrow framing, pacing, and voice cues from the references, but do not copy sentences or facts.",
        "Let preferred reference sources influence hook shape, section progression, and closing pressure.",
        "If a reference cue conflicts with the chosen topic, keep the topic accurate and only absorb the writing pattern.",
    ]

    def build_reference_digest(
        self,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        *,
        limit: int = 3,
    ) -> dict[str, Any]:
        """Return a normalized digest for prompt injection and account context."""

        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        run_strategy = ops_context.get("run_strategy") if isinstance(ops_context.get("run_strategy"), dict) else {}

        preferred_ids = [
            str(item).strip()
            for item in (run_strategy.get("preferred_reference_source_ids") or [])
            if str(item).strip()
        ]
        source_items = account_context.get("reference_source_briefs")
        if not isinstance(source_items, list):
            source_items = account_context.get("reference_sources") or []

        normalized_sources = self._normalize_reference_sources(source_items)
        selected_sources = self._prioritize_reference_sources(
            normalized_sources,
            preferred_ids,
            limit=max(int(limit or 0), 0),
        )

        style_takeaways: list[str] = []
        structure_takeaways: list[str] = []
        for source in selected_sources:
            style_text = source.get("style_clues") or source.get("notes")
            if style_text:
                style_takeaways.append(f"{source['name']}: {style_text}")
            structure_text = source.get("preview") or source.get("resolved_title")
            if structure_text:
                structure_takeaways.append(f"{source['name']}: {structure_text}")

        return {
            "source_count": len(normalized_sources),
            "selected_source_ids": [source["id"] for source in selected_sources if source.get("id")],
            "preferred_source_names": [source["name"] for source in selected_sources if source.get("name")],
            "style_takeaways": style_takeaways[:limit],
            "structure_takeaways": structure_takeaways[:limit],
            "usage_rules": list(self._USAGE_RULES),
            "source_digests": selected_sources,
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
                    "article_count": self._safe_int(item.get("article_count")),
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
        if not sources or limit <= 0:
            return []

        preferred_index = {source_id: index for index, source_id in enumerate(preferred_ids)}

        def _sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
            item_id = self._clean_text(item.get("id"))
            is_preferred = 0 if item_id in preferred_index else 1
            preferred_order = preferred_index.get(item_id, 999)
            return (is_preferred, preferred_order, self._clean_text(item.get("name")))

        return sorted(sources, key=_sort_key)[:limit]

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

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
