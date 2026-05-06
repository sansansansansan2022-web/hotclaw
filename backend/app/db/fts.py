"""SQLite FTS5 setup helpers for memory search.

This module is responsible for ensuring the `article_memories_fts`
virtual table and its synchronization triggers exist. It is idempotent
and safe to call multiple times.

Phase 1 only depends on this for full-text search over article memories.
On non-SQLite databases (e.g. MySQL) FTS5 is silently skipped — callers
must fall back to LIKE-based search.

Failure here MUST NOT block backend startup; we degrade to LIKE fallback.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logger import get_logger

logger = get_logger(__name__)


# All DDL is idempotent. Splitting into a list because some drivers
# refuse multi-statement execute().
_FTS_DDL: list[str] = [
    # Virtual table mirrors the searchable text columns of `article_memories`.
    # `account_id` is UNINDEXED so we filter on it via WHERE without polluting
    # the inverted index. tags / keywords are stored as JSON text in the main
    # table; we copy them verbatim into FTS so substring/character matches work.
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS article_memories_fts USING fts5(
        account_id UNINDEXED,
        title,
        summary,
        content_excerpt,
        tags_text,
        keywords_text,
        content='article_memories',
        content_rowid='id',
        tokenize="unicode61 remove_diacritics 2"
    )
    """,
    # Insert trigger
    """
    CREATE TRIGGER IF NOT EXISTS article_memories_ai
    AFTER INSERT ON article_memories
    BEGIN
        INSERT INTO article_memories_fts(
            rowid, account_id, title, summary, content_excerpt, tags_text, keywords_text
        ) VALUES (
            new.id,
            new.account_id,
            COALESCE(new.title, ''),
            COALESCE(new.summary, ''),
            COALESCE(new.content_excerpt, ''),
            COALESCE(CAST(new.tags AS TEXT), ''),
            COALESCE(CAST(new.keywords AS TEXT), '')
        );
    END
    """,
    # Delete trigger (uses FTS5 'delete' command)
    """
    CREATE TRIGGER IF NOT EXISTS article_memories_ad
    AFTER DELETE ON article_memories
    BEGIN
        INSERT INTO article_memories_fts(
            article_memories_fts, rowid, account_id, title, summary,
            content_excerpt, tags_text, keywords_text
        ) VALUES (
            'delete',
            old.id,
            old.account_id,
            COALESCE(old.title, ''),
            COALESCE(old.summary, ''),
            COALESCE(old.content_excerpt, ''),
            COALESCE(CAST(old.tags AS TEXT), ''),
            COALESCE(CAST(old.keywords AS TEXT), '')
        );
    END
    """,
    # Update trigger: delete-then-insert preserves consistency with FTS5
    # contentless-table semantics.
    """
    CREATE TRIGGER IF NOT EXISTS article_memories_au
    AFTER UPDATE ON article_memories
    BEGIN
        INSERT INTO article_memories_fts(
            article_memories_fts, rowid, account_id, title, summary,
            content_excerpt, tags_text, keywords_text
        ) VALUES (
            'delete',
            old.id,
            old.account_id,
            COALESCE(old.title, ''),
            COALESCE(old.summary, ''),
            COALESCE(old.content_excerpt, ''),
            COALESCE(CAST(old.tags AS TEXT), ''),
            COALESCE(CAST(old.keywords AS TEXT), '')
        );
        INSERT INTO article_memories_fts(
            rowid, account_id, title, summary, content_excerpt, tags_text, keywords_text
        ) VALUES (
            new.id,
            new.account_id,
            COALESCE(new.title, ''),
            COALESCE(new.summary, ''),
            COALESCE(new.content_excerpt, ''),
            COALESCE(CAST(new.tags AS TEXT), ''),
            COALESCE(CAST(new.keywords AS TEXT), '')
        );
    END
    """,
]


def is_sqlite_engine(engine: AsyncEngine) -> bool:
    """Return True when the engine is backed by SQLite."""
    try:
        return engine.url.get_backend_name() == "sqlite"
    except Exception:  # pragma: no cover - defensive
        return False


async def ensure_memory_fts5(engine: AsyncEngine) -> bool:
    """Ensure the `article_memories_fts` virtual table + triggers exist.

    Returns True when FTS5 was successfully provisioned (or already existed).
    Returns False when the engine is non-SQLite or FTS5 is unavailable; the
    memory service must transparently fall back to LIKE-based search.

    This function never raises — failures are logged at WARNING and swallowed
    so a missing FTS5 module cannot break backend startup.
    """
    if not is_sqlite_engine(engine):
        logger.info("memory_fts5_skipped_non_sqlite")
        return False

    try:
        async with engine.begin() as conn:
            # Probe FTS5 availability first. Some custom SQLite builds omit it.
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)"
                )
            )
            await conn.execute(text("DROP TABLE IF EXISTS _fts5_probe"))

            for stmt in _FTS_DDL:
                await conn.execute(text(stmt))

        logger.info("memory_fts5_ready")
        return True
    except Exception as exc:  # pragma: no cover - defensive degradation
        logger.warning(
            "memory_fts5_setup_failed",
            error=str(exc),
            note="memory search will fall back to LIKE",
        )
        return False


async def memory_fts5_available(engine: AsyncEngine) -> bool:
    """Cheap runtime check: does the FTS5 table currently exist?"""
    if not is_sqlite_engine(engine):
        return False
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name='article_memories_fts'"
                    )
                )
            ).first()
            return row is not None
    except Exception as exc:  # pragma: no cover
        logger.warning("memory_fts5_probe_failed", error=str(exc))
        return False
