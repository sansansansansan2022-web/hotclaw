"""Compact reference-source digest helpers for content prompts."""

from __future__ import annotations

from typing import Any


class ReferenceDigestService:
    """Build lightweight, deterministic summaries of account reference sources."""

    def build_reference_digest(
        self,
        *,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        limit: int = 3,
    ) -> dict[str, Any]:
        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        sources = self._normalize_sources(account_context.get("reference_sources"))
        preferred_ids = self._preferred_source_ids(ops_context)
        selected_sources = self._select_sources(sources, preferred_ids, limit=max(0, limit))

        source_digests = [self._build_source_digest(source) for source in selected_sources]
        preferred_names = [
            digest["name"]
            for digest in source_digests
            if digest.get("id") in preferred_ids and digest.get("name")
        ]

        return {
            "source_count": len(sources),
            "selected_source_ids": [digest["id"] for digest in source_digests if digest.get("id")],
            "preferred_source_names": preferred_names,
            "style_takeaways": self._build_style_takeaways(source_digests),
            "structure_takeaways": self._build_structure_takeaways(source_digests),
            "usage_rules": self._build_usage_rules(source_digests, preferred_ids),
            "source_digests": source_digests,
        }

    def _normalize_sources(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _preferred_source_ids(self, ops_context: dict[str, Any]) -> list[str]:
        run_strategy = ops_context.get("run_strategy")
        if not isinstance(run_strategy, dict):
            return []
        preferred = run_strategy.get("preferred_reference_source_ids")
        if not isinstance(preferred, list):
            return []
        return [str(item) for item in preferred if item is not None]

    def _select_sources(
        self,
        sources: list[dict[str, Any]],
        preferred_ids: list[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit == 0:
            return []

        def source_id(source: dict[str, Any]) -> str:
            return str(source.get("id") or source.get("source_id") or "")

        preferred_rank = {source_id: index for index, source_id in enumerate(preferred_ids)}
        preferred_sources = [
            source for source in sources if source_id(source) and source_id(source) in preferred_rank
        ]
        preferred_sources.sort(key=lambda source: preferred_rank[source_id(source)])

        selected: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for source in [*preferred_sources, *sources]:
            current_id = source_id(source)
            dedupe_key = current_id or str(id(source))
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            selected.append(source)
            if len(selected) >= limit:
                break
        return selected

    def _build_source_digest(self, source: dict[str, Any]) -> dict[str, Any]:
        name = self._clean_text(source.get("name") or source.get("title") or "Reference source")
        notes = self._clean_text(source.get("notes") or source.get("description"))
        preview = self._clean_text(
            source.get("preview")
            or source.get("content_preview")
            or source.get("sample")
            or source.get("excerpt")
        )
        return {
            "id": str(source.get("id") or source.get("source_id") or ""),
            "name": name,
            "source_type": self._clean_text(source.get("source_type") or source.get("type")),
            "notes": self._clip_text(notes, 180),
            "preview": self._clip_text(preview, 220),
        }

    def _build_style_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for digest in source_digests:
            name = digest.get("name") or "Reference source"
            notes = digest.get("notes")
            preview = digest.get("preview")
            if notes:
                takeaways.append(f"{name}: {notes}")
            elif preview:
                takeaways.append(f"{name}: mirror the tone implied by this excerpt: {preview}")
        return takeaways

    def _build_structure_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for digest in source_digests:
            name = digest.get("name") or "Reference source"
            preview = digest.get("preview")
            if preview:
                takeaways.append(f"{name}: use the excerpt as a structural reference, not source text.")
        return takeaways

    def _build_usage_rules(
        self,
        source_digests: list[dict[str, Any]],
        preferred_ids: list[str],
    ) -> list[str]:
        if not source_digests:
            return []
        rules = [
            "Use reference sources for tone, pacing, and structure only; do not copy source wording.",
            "Prioritize preferred reference sources when they are present.",
        ]
        if preferred_ids:
            rules.append(f"Preferred reference source ids: {', '.join(preferred_ids)}.")
        return rules

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
