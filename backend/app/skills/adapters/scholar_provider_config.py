"""Shared scholar provider parsing helpers."""

from __future__ import annotations

import re


def parse_scholar_provider_tokens(provider: str | None) -> set[str]:
    """Parse SCHOLAR_PROVIDER into normalized source tokens."""

    raw = str(provider or "").strip().lower()
    if not raw:
        return set()
    normalized = raw.replace("semantic-scholar", "semanticscholar").replace("semantic_scholar", "semanticscholar")
    parts = [item.strip() for item in re.split(r"[^a-z0-9_]+", normalized) if item.strip()]
    aliases = {
        "oa": "openalex",
        "cr": "crossref",
        "s2": "semanticscholar",
        "semantic": "semanticscholar",
        "pm": "pubmed",
    }
    return {aliases.get(item, item) for item in parts}


def provider_includes(provider: str | None, *tokens: str) -> bool:
    parsed = parse_scholar_provider_tokens(provider)
    if not parsed:
        return False
    expected = {token.strip().lower() for token in tokens if token.strip()}
    return any(token in parsed for token in expected)
