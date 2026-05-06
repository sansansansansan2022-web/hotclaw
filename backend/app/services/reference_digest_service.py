"""Reference digest service.

NOTE: This is a minimal placeholder implementation added to unblock backend
startup. The original `reference_digest_service` module is referenced from
`article_assembler_service` but is missing from the repository snapshot.

The placeholder returns an empty digest with the schema expected by the
caller. When real reference-source aggregation logic is required, replace
the body of `build_reference_digest` to derive style/structure takeaways
from `account_context["reference_sources"]` and `ops_context`.
"""

from __future__ import annotations

from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class ReferenceDigestService:
    """Build a compact reference digest consumed by content agents."""

    def build_reference_digest(
        self,
        *,
        account_context: dict[str, Any] | None = None,
        ops_context: dict[str, Any] | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        sources = self._extract_sources(account_context)
        selected = sources[: max(0, int(limit or 0))]

        digest: dict[str, Any] = {
            "source_count": len(sources),
            "selected_source_ids": [self._source_id(item) for item in selected],
            "preferred_source_names": [self._source_name(item) for item in selected],
            "style_takeaways": [],
            "structure_takeaways": [],
            "usage_rules": [],
            "source_digests": [self._source_digest(item) for item in selected],
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
        raw = account_context.get("reference_sources")
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

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
            "preview": source.get("preview") or "",
        }


reference_digest_service = ReferenceDigestService()
