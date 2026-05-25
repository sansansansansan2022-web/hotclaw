"""Build compact reference-source digests for content prompts."""

from __future__ import annotations

import re
from typing import Any


class ReferenceDigestService:
    """Normalize account reference sources into stable prompt-sized briefs."""

    def build_reference_digest(
        self,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        *,
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
        selected_sources = self._select_sources(sources, preferred_ids, limit=max(0, limit))
        source_digests = [self._digest_source(source) for source in selected_sources]

        return {
            "source_count": len(sources),
            "selected_source_ids": [item["id"] for item in source_digests if item.get("id")],
            "preferred_source_names": [item["name"] for item in source_digests if item.get("name")],
            "style_takeaways": self._build_style_takeaways(source_digests),
            "structure_takeaways": self._build_structure_takeaways(source_digests),
            "usage_rules": self._build_usage_rules(source_digests),
            "source_digests": source_digests,
        }

    def _preferred_source_ids(self, ops_context: dict[str, Any]) -> list[str]:
        run_strategy = ops_context.get("run_strategy")
        if not isinstance(run_strategy, dict):
            return []
        return [
            str(item).strip()
            for item in run_strategy.get("preferred_reference_source_ids", [])
            if str(item).strip()
        ]

    def _select_sources(
        self,
        sources: list[dict[str, Any]],
        preferred_ids: list[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit == 0:
            return []

        by_id = {str(source.get("id")): source for source in sources if source.get("id") is not None}
        selected: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for source_id in preferred_ids:
            source = by_id.get(source_id)
            if not source or source_id in seen_ids:
                continue
            selected.append(source)
            seen_ids.add(source_id)
            if len(selected) >= limit:
                return selected

        for source in sources:
            source_id = str(source.get("id")) if source.get("id") is not None else ""
            if source_id and source_id in seen_ids:
                continue
            selected.append(source)
            if source_id:
                seen_ids.add(source_id)
            if len(selected) >= limit:
                break

        return selected

    def _digest_source(self, source: dict[str, Any]) -> dict[str, Any]:
        metadata = source.get("metadata_json") if isinstance(source.get("metadata_json"), dict) else {}
        preview = (
            source.get("preview")
            or metadata.get("preview")
            or metadata.get("resolved_title")
            or source.get("source_value")
        )
        return {
            "id": str(source.get("id")) if source.get("id") is not None else None,
            "name": self._clean_text(source.get("name")),
            "source_type": self._clean_text(source.get("source_type")),
            "sync_status": self._clean_text(source.get("sync_status")),
            "article_count": int(source.get("article_count") or 0),
            "resolved_title": self._clean_text(source.get("resolved_title") or metadata.get("resolved_title")),
            "notes": self._clip_text(source.get("notes"), 180),
            "preview": self._clip_text(preview, 240),
        }

    def _build_style_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in source_digests:
            name = source.get("name") or "Reference source"
            notes = source.get("notes")
            preview = source.get("preview")
            if notes:
                takeaways.append(f"{name}: {notes}")
            elif preview:
                takeaways.append(f"{name}: use the pacing and emphasis implied by this excerpt: {preview}")
        return takeaways

    def _build_structure_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in source_digests:
            name = source.get("name") or "Reference source"
            preview = source.get("preview")
            if preview:
                takeaways.append(f"{name}: mirror the opening, turn, and closing rhythm without copying text.")
        return takeaways

    def _build_usage_rules(self, source_digests: list[dict[str, Any]]) -> list[str]:
        if not source_digests:
            return ["No account reference sources are available; rely on the account positioning and topic package."]
        return [
            "Use reference sources as style and structure guidance, not as text to copy.",
            "Prefer the selected reference sources when the ops strategy names preferred IDs.",
            "Preserve the current article topic even when borrowing rhythm from references.",
        ]

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return re.sub(r"\s+", " ", text)

    def _clip_text(self, value: Any, limit: int) -> str:
        text = self._clean_text(value)
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."


reference_digest_service = ReferenceDigestService()
