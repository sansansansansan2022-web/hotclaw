"""Reference source digest generation for content prompts."""

from __future__ import annotations

from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class ReferenceDigestService:
    """Build compact reference-source summaries consumed by content agents."""

    def build_reference_digest(
        self,
        *,
        account_context: dict[str, Any] | None = None,
        ops_context: dict[str, Any] | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        sources = self._extract_sources(account_context)
        ordered_sources = self._order_by_preferences(sources, ops_context)
        selected = ordered_sources[: max(0, int(limit or 0))]

        digest = {
            "source_count": len(sources),
            "selected_source_ids": [self._source_id(source) for source in selected],
            "preferred_source_names": [self._source_name(source) for source in selected],
            "style_takeaways": self._style_takeaways(selected),
            "structure_takeaways": self._structure_takeaways(selected),
            "usage_rules": self._usage_rules(selected),
            "source_digests": [self._source_digest(source) for source in selected],
        }
        logger.debug(
            "reference_digest_built",
            source_count=digest["source_count"],
            selected=len(selected),
            limit=limit,
        )
        return digest

    @staticmethod
    def _extract_sources(account_context: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(account_context, dict):
            return []
        sources = account_context.get("reference_sources")
        if not isinstance(sources, list):
            return []
        return [source for source in sources if isinstance(source, dict)]

    @staticmethod
    def _order_by_preferences(
        sources: list[dict[str, Any]],
        ops_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if not sources or not isinstance(ops_context, dict):
            return sources

        run_strategy = ops_context.get("run_strategy")
        if not isinstance(run_strategy, dict):
            return sources

        preferred_ids = run_strategy.get("preferred_reference_source_ids") or []
        if not isinstance(preferred_ids, list) or not preferred_ids:
            return sources

        preferred_order = {str(source_id): index for index, source_id in enumerate(preferred_ids)}

        def sort_key(source: dict[str, Any]) -> tuple[int, int]:
            source_id = ReferenceDigestService._source_id(source)
            if source_id in preferred_order:
                return (0, preferred_order[source_id])
            return (1, 0)

        return sorted(sources, key=sort_key)

    @staticmethod
    def _style_takeaways(sources: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in sources:
            name = ReferenceDigestService._source_name(source)
            notes = ReferenceDigestService._clean_text(source.get("notes"))
            preview = ReferenceDigestService._clean_text(source.get("preview"))
            if name and notes:
                takeaways.append(f"{name}: {notes}")
            elif name and preview:
                takeaways.append(f"{name}: {preview}")
        return takeaways

    @staticmethod
    def _structure_takeaways(sources: list[dict[str, Any]]) -> list[str]:
        takeaways: list[str] = []
        for source in sources:
            metadata = source.get("metadata_json")
            if not isinstance(metadata, dict):
                metadata = {}
            for key in ("structure_takeaway", "structure_takeaways"):
                value = metadata.get(key)
                if isinstance(value, str) and value.strip():
                    takeaways.append(value.strip())
                elif isinstance(value, list):
                    takeaways.extend(str(item).strip() for item in value if str(item).strip())
        return takeaways

    @staticmethod
    def _usage_rules(sources: list[dict[str, Any]]) -> list[str]:
        rules: list[str] = []
        for source in sources:
            metadata = source.get("metadata_json")
            if not isinstance(metadata, dict):
                metadata = {}
            value = metadata.get("usage_rules") or metadata.get("usage_rule")
            if isinstance(value, str) and value.strip():
                rules.append(value.strip())
            elif isinstance(value, list):
                rules.extend(str(item).strip() for item in value if str(item).strip())
        return rules

    @staticmethod
    def _source_id(source: dict[str, Any]) -> str:
        for key in ("id", "source_id", "uuid"):
            value = source.get(key)
            if value is not None:
                return str(value)
        return ""

    @staticmethod
    def _source_name(source: dict[str, Any]) -> str:
        for key in ("name", "title", "source_value"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _source_digest(source: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": ReferenceDigestService._source_id(source),
            "name": ReferenceDigestService._source_name(source),
            "source_type": source.get("source_type"),
            "preview": ReferenceDigestService._clean_text(source.get("preview")),
        }

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split()).strip()


reference_digest_service = ReferenceDigestService()
