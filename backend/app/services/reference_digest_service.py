"""Build compact reference-source briefs for article generation."""

from __future__ import annotations

import re
from typing import Any


class ReferenceDigestService:
    """Normalize account reference sources into a prompt-safe style digest."""

    def build_reference_digest(
        self,
        *,
        account_context: dict[str, Any] | None,
        ops_context: dict[str, Any] | None,
        limit: int = 3,
    ) -> dict[str, Any]:
        sources = self._normalize_sources(account_context)
        preferred_ids = self._preferred_source_ids(ops_context)
        selected_sources = self._select_sources(sources, preferred_ids, limit)

        source_digests = [self._build_source_digest(source) for source in selected_sources]
        preferred_names = [digest["name"] for digest in source_digests if digest.get("name")]

        return {
            "source_count": len(sources),
            "selected_source_ids": [digest["id"] for digest in source_digests if digest.get("id")],
            "preferred_source_names": preferred_names,
            "style_takeaways": self._build_style_takeaways(source_digests),
            "structure_takeaways": self._build_structure_takeaways(source_digests),
            "usage_rules": self._build_usage_rules(source_digests),
            "source_digests": source_digests,
        }

    def _normalize_sources(self, account_context: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(account_context, dict):
            return []

        raw_sources = account_context.get("reference_sources")
        if not isinstance(raw_sources, list):
            return []

        sources: list[dict[str, Any]] = []
        for raw_source in raw_sources:
            if not isinstance(raw_source, dict):
                continue

            source_id = self._clean_text(raw_source.get("id"))
            name = self._clean_text(raw_source.get("name")) or self._fallback_name(raw_source)
            source_type = self._clean_text(raw_source.get("source_type"))
            metadata = (
                raw_source.get("metadata_json")
                if isinstance(raw_source.get("metadata_json"), dict)
                else {}
            )
            preview = (
                raw_source.get("preview")
                or metadata.get("preview")
                or raw_source.get("source_value")
                or ""
            )

            sources.append(
                {
                    "id": source_id,
                    "name": name,
                    "source_type": source_type,
                    "notes": self._clean_text(raw_source.get("notes")),
                    "preview": self._clip_text(preview, 220),
                    "resolved_title": self._clean_text(
                        raw_source.get("resolved_title") or metadata.get("resolved_title")
                    ),
                    "sync_status": self._clean_text(raw_source.get("sync_status")),
                    "article_count": int(raw_source.get("article_count") or 0),
                }
            )

        return sources

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
            if not source_id or source_id in seen:
                continue
            preferred_ids.append(source_id)
            seen.add(source_id)
        return preferred_ids

    def _select_sources(
        self,
        sources: list[dict[str, Any]],
        preferred_ids: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        safe_limit = max(0, int(limit or 0))
        if safe_limit == 0:
            return []

        by_id = {source["id"]: source for source in sources if source.get("id")}
        selected: list[dict[str, Any]] = []
        selected_ids: set[str] = set()

        for preferred_id in preferred_ids:
            source = by_id.get(preferred_id)
            if not source or preferred_id in selected_ids:
                continue
            selected.append(source)
            selected_ids.add(preferred_id)
            if len(selected) >= safe_limit:
                return selected

        for source in sources:
            source_id = source.get("id")
            dedupe_key = source_id or source.get("name") or str(id(source))
            if dedupe_key in selected_ids:
                continue
            selected.append(source)
            selected_ids.add(dedupe_key)
            if len(selected) >= safe_limit:
                break

        return selected

    def _build_source_digest(self, source: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": source.get("id") or "",
            "name": source.get("name") or "Reference Source",
            "source_type": source.get("source_type") or "unknown",
            "notes": self._clip_text(source.get("notes"), 180),
            "preview": self._clip_text(source.get("preview"), 220),
            "resolved_title": source.get("resolved_title") or "",
            "sync_status": source.get("sync_status") or "",
            "article_count": int(source.get("article_count") or 0),
        }

    def _build_style_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for digest in source_digests:
            name = digest.get("name") or "Reference Source"
            notes = digest.get("notes")
            preview = digest.get("preview")
            if notes:
                takeaways.append(f"{name}: use the voice cues from its notes - {notes}")
            elif preview:
                takeaways.append(f"{name}: echo the cadence and specificity suggested by the preview.")
            else:
                takeaways.append(f"{name}: use as a directional style reference without copying wording.")
        return takeaways

    def _build_structure_takeaways(self, source_digests: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for digest in source_digests:
            name = digest.get("name") or "Reference Source"
            preview = digest.get("preview")
            title = digest.get("resolved_title")
            if preview:
                takeaways.append(f"{name}: study how the sample opens, turns, and lands; do not reuse its facts.")
            elif title:
                takeaways.append(f"{name}: use the resolved title as a structural signal, not as source material.")
        return takeaways

    def _build_usage_rules(self, source_digests: list[dict[str, Any]]) -> list[str]:
        if not source_digests:
            return []
        return [
            "Use reference sources for voice, structure, and editorial standards only.",
            (
                "Do not copy source wording, claims, examples, or facts unless they are "
                "independently present in the task context."
            ),
            "Prefer the explicitly selected reference sources before other account references.",
        ]

    def _fallback_name(self, raw_source: dict[str, Any]) -> str:
        source_type = self._clean_text(raw_source.get("source_type"))
        source_value = self._clean_text(raw_source.get("source_value"))
        if source_type == "article_url":
            return "Article URL Source"
        if source_type == "wechat_account" and source_value:
            return self._clip_text(source_value, 120)
        if source_value:
            return self._clip_text(source_value, 60)
        return "Reference Source"

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
