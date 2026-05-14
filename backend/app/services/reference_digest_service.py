"""Reference source digest helpers for article-generation prompts."""

from __future__ import annotations

import re
from typing import Any


class ReferenceDigestService:
    """Build compact, deterministic style briefs from account reference sources."""

    def build_reference_digest(
        self,
        *,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        limit: int = 3,
    ) -> dict[str, Any]:
        account_context = account_context if isinstance(account_context, dict) else {}
        ops_context = ops_context if isinstance(ops_context, dict) else {}
        references = self._normalize_references(account_context.get("reference_sources"))
        ordered_references = self._prioritize_references(
            references,
            self._preferred_reference_ids(ops_context),
        )
        selected = ordered_references[: max(0, limit)]

        return {
            "source_count": len(references),
            "selected_source_ids": [item["id"] for item in selected if item.get("id")],
            "preferred_source_names": [item["name"] for item in selected if item.get("name")],
            "style_takeaways": self._build_style_takeaways(selected),
            "structure_takeaways": self._build_structure_takeaways(selected),
            "usage_rules": self._build_usage_rules(selected),
            "source_digests": [self._source_digest(item) for item in selected],
        }

    def _normalize_references(self, raw_sources: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_sources, list):
            return []

        references: list[dict[str, Any]] = []
        for index, item in enumerate(raw_sources):
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata_json") if isinstance(item.get("metadata_json"), dict) else {}
            preview = (
                item.get("preview")
                or metadata.get("preview")
                or metadata.get("summary")
                or (item.get("source_value") if item.get("source_type") == "pasted_article" else None)
            )
            source_id = self._clean_text(item.get("id")) or f"reference-{index + 1}"
            references.append(
                {
                    "id": source_id,
                    "name": self._clean_text(item.get("name")) or f"Reference {index + 1}",
                    "source_type": self._clean_text(item.get("source_type")) or "reference",
                    "notes": self._clean_text(item.get("notes")),
                    "preview": self._clean_text(preview),
                    "resolved_title": self._clean_text(metadata.get("resolved_title")),
                }
            )
        return references

    def _preferred_reference_ids(self, ops_context: dict[str, Any]) -> list[str]:
        run_strategy = ops_context.get("run_strategy")
        if not isinstance(run_strategy, dict):
            return []
        raw_ids = run_strategy.get("preferred_reference_source_ids")
        if not isinstance(raw_ids, list):
            return []
        return [str(item) for item in raw_ids if item is not None]

    def _prioritize_references(
        self,
        references: list[dict[str, Any]],
        preferred_ids: list[str],
    ) -> list[dict[str, Any]]:
        preferred_rank = {source_id: index for index, source_id in enumerate(preferred_ids)}
        ranked = sorted(
            enumerate(references),
            key=lambda pair: (
                preferred_rank.get(str(pair[1].get("id")), len(preferred_rank)),
                pair[0],
            ),
        )
        return [item for _, item in ranked]

    def _build_style_takeaways(self, references: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for item in references:
            source_text = self._join_fragments(item.get("notes"), item.get("preview"))
            if not source_text:
                continue
            takeaways.append(
                f"{item['name']}: mirror its tone cues - {self._clip_text(source_text, 160)}"
            )
        return takeaways

    def _build_structure_takeaways(self, references: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for item in references:
            source_text = self._join_fragments(item.get("resolved_title"), item.get("preview"))
            if not source_text:
                continue
            takeaways.append(
                f"{item['name']}: use its opening/argument flow as structure reference - "
                f"{self._clip_text(source_text, 140)}"
            )
        return takeaways

    def _build_usage_rules(self, references: list[dict[str, Any]]) -> list[str]:
        if not references:
            return []
        return [
            "Use reference sources for style, structure, and evidence patterns; do not copy source wording.",
            "Prefer explicitly selected references first when resolving tone or structure conflicts.",
        ]

    def _source_digest(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "source_type": item.get("source_type"),
            "notes": self._clip_text(item.get("notes"), 180),
            "preview": self._clip_text(item.get("preview"), 240),
        }

    def _join_fragments(self, *values: Any) -> str:
        return " ".join(value for value in (self._clean_text(item) for item in values) if value)

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _clip_text(self, value: Any, limit: int) -> str:
        text = self._clean_text(value)
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."


reference_digest_service = ReferenceDigestService()
