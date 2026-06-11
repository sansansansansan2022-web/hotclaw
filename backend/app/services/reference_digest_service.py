"""Reference source digest helpers for content-generation prompts."""

from __future__ import annotations

from typing import Any


class ReferenceDigestService:
    """Build compact, deterministic summaries of account reference sources."""

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
        selected = self._select_sources(sources, preferred_ids, limit=max(0, int(limit or 0)))

        source_digests = [self._source_digest(source) for source in selected]
        preferred_names = [digest["name"] for digest in source_digests if digest.get("name")]
        style_takeaways = [
            self._format_takeaway(digest)
            for digest in source_digests
            if self._format_takeaway(digest)
        ]
        structure_takeaways = [
            f"Mirror the structure cues from {digest['name']}: {digest['preview']}"
            for digest in source_digests
            if digest.get("name") and digest.get("preview")
        ]

        usage_rules = []
        if source_digests:
            usage_rules.append("Use reference sources for style and structure guidance without copying wording.")
            usage_rules.append("Prefer explicitly selected reference sources when they are available.")

        return {
            "source_count": len(sources),
            "selected_source_ids": [digest["id"] for digest in source_digests],
            "preferred_source_names": preferred_names,
            "style_takeaways": style_takeaways,
            "structure_takeaways": structure_takeaways,
            "usage_rules": usage_rules,
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
        raw_ids = run_strategy.get("preferred_reference_source_ids")
        if not isinstance(raw_ids, list):
            return []
        return [str(item) for item in raw_ids if str(item).strip()]

    def _select_sources(
        self,
        sources: list[dict[str, Any]],
        preferred_ids: list[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        by_id = {str(source.get("id")): source for source in sources if source.get("id") is not None}
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()

        for source_id in preferred_ids:
            source = by_id.get(source_id)
            if source is None or source_id in seen:
                continue
            selected.append(source)
            seen.add(source_id)
            if len(selected) >= limit:
                return selected

        for source in sources:
            source_id = str(source.get("id"))
            if source_id in seen:
                continue
            selected.append(source)
            seen.add(source_id)
            if len(selected) >= limit:
                break

        return selected

    def _source_digest(self, source: dict[str, Any]) -> dict[str, Any]:
        name = self._clean_text(source.get("name") or source.get("resolved_title") or "Reference")
        notes = self._clean_text(source.get("notes"))
        preview = self._clean_text(
            source.get("preview")
            or source.get("excerpt")
            or source.get("summary")
            or source.get("source_value")
        )
        return {
            "id": str(source.get("id")) if source.get("id") is not None else "",
            "name": name,
            "source_type": self._clean_text(source.get("source_type")),
            "notes": self._clip(notes, 180),
            "preview": self._clip(preview, 220),
        }

    def _format_takeaway(self, digest: dict[str, Any]) -> str:
        name = digest.get("name")
        detail = digest.get("notes") or digest.get("preview")
        if not name or not detail:
            return ""
        return f"{name}: {detail}"

    def _clean_text(self, value: Any) -> str:
        return " ".join(str(value or "").split())

    def _clip(self, value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 1)].rstrip() + "..."


reference_digest_service = ReferenceDigestService()
