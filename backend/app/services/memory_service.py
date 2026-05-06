"""Account-scoped article memory service (Phase 1).

Responsibilities:
1. CRUD-ish access to `article_memories` for the frontend memory page.
2. Distill `article_drafts` (status=published) into compact memory entries.
3. Provide `retrieve_relevant()` so Phase 2 can inject prior-work snippets
   into agent prompts (interface only — no agent integration here).

Search strategy (SQLite):
- When `article_memories_fts` (FTS5) exists, run a MATCH query and intersect
  with the `account_id` filter; otherwise fall back to a `LIKE` scan.
- For non-SQLite engines, FTS5 is unavailable, so the LIKE fallback applies.

The service exposes both an instance (`memory_service`) and a module-level
namespace, mirroring other services in `app/services/`.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, func as sa_func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.db.fts import is_sqlite_engine, memory_fts5_available
from app.models.tables import AccountModel, ArticleDraftModel, ArticleMemoryModel

logger = get_logger(__name__)


# Excerpt length cap — keeps memory rows small enough to fit dozens into
# a single LLM context window during Phase 2 retrieval.
_EXCERPT_MAX_CHARS = 600
_SUMMARY_MAX_CHARS = 280


# --- helpers -----------------------------------------------------------------


def _strip_markdown(text_value: str) -> str:
    """Cheap markdown stripper used to build a readable excerpt.

    We are not aiming for perfect output — just removing the most disruptive
    markup so the excerpt looks reasonable in the UI and is searchable.
    """
    if not text_value:
        return ""
    cleaned = text_value
    # Headings, blockquotes, list bullets, table pipes
    cleaned = re.sub(r"^\s{0,3}(#{1,6}\s+|>\s+|[-*+]\s+|\d+\.\s+)", "", cleaned, flags=re.MULTILINE)
    # Bold / italic markers
    cleaned = re.sub(r"\*{1,3}|_{1,3}", "", cleaned)
    # Inline code / code fences
    cleaned = re.sub(r"`{1,3}[^`]*`{1,3}", " ", cleaned)
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.DOTALL)
    # Links: keep label only
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    # Images
    cleaned = re.sub(r"!\[[^\]]*\]\([^\)]+\)", " ", cleaned)
    # Excessive whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _build_memory_payload(draft: ArticleDraftModel) -> dict[str, Any]:
    """Distill a published draft into a memory row payload."""
    excerpt_source = (draft.content_markdown or "").strip()
    excerpt = _strip_markdown(excerpt_source)[:_EXCERPT_MAX_CHARS] or None

    summary = draft.summary
    if summary and len(summary) > _SUMMARY_MAX_CHARS:
        summary = summary[:_SUMMARY_MAX_CHARS].rstrip() + "…"

    tags = draft.tags if isinstance(draft.tags, list) else None

    metadata: dict[str, Any] = {
        "draft_status": draft.draft_status,
        "publish_status": draft.publish_status,
        "word_count": draft.word_count,
        "source_type": draft.source_type,
    }
    if draft.selected_topic:
        metadata["selected_topic"] = draft.selected_topic

    return {
        "account_id": draft.account_id,
        "source_draft_id": draft.id,
        "source_task_id": draft.task_id,
        # `article_id` is reserved for an external CMS id when the draft
        # is published to a real platform — leave None for now.
        "article_id": None,
        "title": draft.title or "(untitled)",
        "summary": summary,
        "content_excerpt": excerpt,
        "tags": tags,
        "keywords": None,
        "metadata_json": metadata,
        "published_at": draft.published_at,
    }


def _is_published(draft: ArticleDraftModel) -> bool:
    """Treat a draft as 'published' for memory purposes when any signal aligns.

    The user's spec says `status='published'` but the schema uses three
    different status columns; we accept the broadest definition that still
    means "actually shipped".
    """
    if draft.publish_status and draft.publish_status.lower() == "published":
        return True
    if draft.status and draft.status.lower() == "published":
        return True
    return False


# --- service -----------------------------------------------------------------


class MemoryService:
    """High-level operations for account-scoped article memories."""

    # ----- account guard -----------------------------------------------------

    async def _ensure_account(self, account_id: str, db: AsyncSession) -> AccountModel:
        result = await db.execute(
            select(AccountModel).where(AccountModel.id == account_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    # ----- read --------------------------------------------------------------

    async def list_article_memories(
        self,
        account_id: str,
        query: str | None,
        page: int,
        page_size: int,
        db: AsyncSession,
    ) -> tuple[list[ArticleMemoryModel], int]:
        """Paginated/searched listing for the frontend memory page.

        - Empty query → plain `WHERE account_id=?` scan ordered by recency.
        - Non-empty query → FTS5 MATCH when available; LIKE fallback otherwise.
        """
        await self._ensure_account(account_id, db)

        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 100))
        offset = (page - 1) * page_size

        normalized_query = (query or "").strip()

        if not normalized_query:
            return await self._list_paginated(account_id, page_size, offset, db)

        ids: list[int] | None = None
        engine = db.get_bind()
        try:
            use_fts = await memory_fts5_available(engine)
        except Exception:
            use_fts = False

        if use_fts:
            try:
                ids = await self._fts_search_ids(account_id, normalized_query, db)
            except Exception as exc:
                logger.warning(
                    "memory_fts_query_failed",
                    account_id=account_id,
                    error=str(exc),
                    note="falling back to LIKE",
                )
                ids = None

        if ids is None:
            return await self._like_search(
                account_id, normalized_query, page_size, offset, db
            )

        if not ids:
            return [], 0

        total = len(ids)
        page_ids = ids[offset : offset + page_size]
        if not page_ids:
            return [], total

        rows = (
            await db.execute(
                select(ArticleMemoryModel).where(ArticleMemoryModel.id.in_(page_ids))
            )
        ).scalars().all()
        # Preserve FTS rank ordering by reindexing on returned ids.
        order_index = {mid: idx for idx, mid in enumerate(page_ids)}
        rows.sort(key=lambda m: order_index.get(m.id, 1_000_000))
        return list(rows), total

    async def get_article_memory(
        self, memory_id: int, db: AsyncSession
    ) -> ArticleMemoryModel | None:
        result = await db.execute(
            select(ArticleMemoryModel).where(ArticleMemoryModel.id == memory_id)
        )
        return result.scalar_one_or_none()

    # ----- distillation ------------------------------------------------------

    async def rebuild_article_memories(
        self, account_id: str, db: AsyncSession
    ) -> dict[str, Any]:
        """Wipe and re-create memories from every published draft on the account."""
        await self._ensure_account(account_id, db)

        # Truncate existing memories for this account.
        existing_ids = (
            await db.execute(
                select(ArticleMemoryModel.id).where(
                    ArticleMemoryModel.account_id == account_id
                )
            )
        ).scalars().all()
        for old in existing_ids:
            obj = await db.get(ArticleMemoryModel, old)
            if obj is not None:
                await db.delete(obj)
        # Flush deletions so triggers (FTS sync) fire before re-inserts.
        await db.flush()

        drafts = await self._fetch_published_drafts(account_id, db)
        created = 0
        for draft in drafts:
            payload = _build_memory_payload(draft)
            db.add(ArticleMemoryModel(**payload))
            created += 1

        await db.commit()
        logger.info(
            "memory_rebuild_complete",
            account_id=account_id,
            drafts_processed=len(drafts),
            created=created,
            removed=len(existing_ids),
        )
        return {
            "processed": len(drafts),
            "created": created,
            "removed": len(existing_ids),
            "message": f"rebuilt {created} memories from {len(drafts)} published drafts",
        }

    async def sync_article_memories(
        self, account_id: str, db: AsyncSession
    ) -> dict[str, Any]:
        """Incremental sync — only distill drafts not yet seen.

        We anti-join `article_memories.source_draft_id` to find published
        drafts that have never been materialized. Order by recency so that
        the earliest unseen drafts get their memories first.
        """
        await self._ensure_account(account_id, db)

        existing_draft_ids = set(
            (
                await db.execute(
                    select(ArticleMemoryModel.source_draft_id).where(
                        and_(
                            ArticleMemoryModel.account_id == account_id,
                            ArticleMemoryModel.source_draft_id.is_not(None),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )

        drafts = await self._fetch_published_drafts(account_id, db)
        new_drafts = [d for d in drafts if d.id not in existing_draft_ids]

        created = 0
        for draft in new_drafts:
            payload = _build_memory_payload(draft)
            db.add(ArticleMemoryModel(**payload))
            created += 1

        await db.commit()
        logger.info(
            "memory_sync_complete",
            account_id=account_id,
            drafts_processed=len(new_drafts),
            created=created,
            already_present=len(existing_draft_ids),
        )
        return {
            "processed": len(new_drafts),
            "created": created,
            "skipped": len(drafts) - len(new_drafts),
            "message": f"synced {created} new memories ({len(drafts) - len(new_drafts)} already present)",
        }

    # ----- retrieval (Phase 2 entry point) -----------------------------------

    async def retrieve_relevant(
        self,
        account_id: str,
        query: str,
        db: AsyncSession,
        limit: int = 5,
    ) -> list[ArticleMemoryModel]:
        """Return the top-N memories most relevant to `query` for an account.

        Phase 2 (orchestrator/agents) will call this to inject prior-work
        snippets into prompts. For Phase 1 we only need the implementation
        to exist and be callable; behaviour matches `list_article_memories`
        with a smaller limit and rank-preserving order.
        """
        normalized = (query or "").strip()
        limit = max(1, min(int(limit or 5), 20))

        if not normalized:
            rows = (
                await db.execute(
                    select(ArticleMemoryModel)
                    .where(ArticleMemoryModel.account_id == account_id)
                    .order_by(
                        desc(ArticleMemoryModel.published_at),
                        desc(ArticleMemoryModel.created_at),
                    )
                    .limit(limit)
                )
            ).scalars().all()
            return list(rows)

        engine = db.get_bind()
        try:
            use_fts = await memory_fts5_available(engine)
        except Exception:
            use_fts = False

        if use_fts:
            try:
                ids = await self._fts_search_ids(
                    account_id, normalized, db, limit=limit
                )
            except Exception as exc:
                logger.warning(
                    "memory_retrieve_fts_failed",
                    account_id=account_id,
                    error=str(exc),
                )
                ids = None
            if ids is not None:
                if not ids:
                    return []
                rows = (
                    await db.execute(
                        select(ArticleMemoryModel).where(
                            ArticleMemoryModel.id.in_(ids)
                        )
                    )
                ).scalars().all()
                order_index = {mid: idx for idx, mid in enumerate(ids)}
                rows.sort(key=lambda m: order_index.get(m.id, 1_000_000))
                return list(rows[:limit])

        rows, _ = await self._like_search(account_id, normalized, limit, 0, db)
        return list(rows)

    # ----- internals ---------------------------------------------------------

    async def _list_paginated(
        self,
        account_id: str,
        page_size: int,
        offset: int,
        db: AsyncSession,
    ) -> tuple[list[ArticleMemoryModel], int]:
        total_stmt = (
            select(sa_func.count(ArticleMemoryModel.id))
            .where(ArticleMemoryModel.account_id == account_id)
        )
        total = (await db.execute(total_stmt)).scalar_one()

        rows_stmt = (
            select(ArticleMemoryModel)
            .where(ArticleMemoryModel.account_id == account_id)
            .order_by(
                desc(ArticleMemoryModel.published_at),
                desc(ArticleMemoryModel.created_at),
                desc(ArticleMemoryModel.id),
            )
            .limit(page_size)
            .offset(offset)
        )
        rows = (await db.execute(rows_stmt)).scalars().all()
        return list(rows), int(total)

    async def _like_search(
        self,
        account_id: str,
        query: str,
        page_size: int,
        offset: int,
        db: AsyncSession,
    ) -> tuple[list[ArticleMemoryModel], int]:
        like_pattern = f"%{query}%"
        condition = and_(
            ArticleMemoryModel.account_id == account_id,
            or_(
                ArticleMemoryModel.title.ilike(like_pattern),
                ArticleMemoryModel.summary.ilike(like_pattern),
                ArticleMemoryModel.content_excerpt.ilike(like_pattern),
            ),
        )
        total = (
            await db.execute(
                select(sa_func.count(ArticleMemoryModel.id)).where(condition)
            )
        ).scalar_one()

        rows = (
            await db.execute(
                select(ArticleMemoryModel)
                .where(condition)
                .order_by(
                    desc(ArticleMemoryModel.published_at),
                    desc(ArticleMemoryModel.created_at),
                    desc(ArticleMemoryModel.id),
                )
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
        return list(rows), int(total)

    async def _fts_search_ids(
        self,
        account_id: str,
        query: str,
        db: AsyncSession,
        limit: int | None = None,
    ) -> list[int]:
        """Run an FTS5 MATCH query and return rowids ordered by rank.

        We deliberately use a parameterized "match expression" — for
        unicode61-tokenized Chinese, the simplest robust strategy is to
        wrap each whitespace-separated chunk in double quotes so users can
        paste raw substrings without worrying about FTS5 operator syntax.
        """
        match_expr = self._build_match_expression(query)
        if not match_expr:
            return []

        engine = db.get_bind()
        if not is_sqlite_engine(engine):
            return []

        sql = text(
            "SELECT rowid FROM article_memories_fts "
            "WHERE article_memories_fts MATCH :q AND account_id = :acc "
            "ORDER BY rank"
            + (" LIMIT :lim" if limit else "")
        )
        params: dict[str, Any] = {"q": match_expr, "acc": account_id}
        if limit:
            params["lim"] = int(limit)

        result = await db.execute(sql, params)
        return [int(r[0]) for r in result.all()]

    @staticmethod
    def _build_match_expression(query: str) -> str:
        """Translate a user query into a safe FTS5 MATCH expression.

        Strategy: split on whitespace, double-quote each token (escaping
        embedded quotes), join with implicit AND. This avoids FTS5 syntax
        errors when users type punctuation or Chinese substrings.
        """
        tokens = [t for t in re.split(r"\s+", query.strip()) if t]
        if not tokens:
            return ""
        quoted: list[str] = []
        for tok in tokens:
            escaped = tok.replace('"', '""')
            quoted.append(f'"{escaped}"')
        return " ".join(quoted)

    async def _fetch_published_drafts(
        self, account_id: str, db: AsyncSession
    ) -> list[ArticleDraftModel]:
        """Return all drafts for an account that we treat as published.

        See `_is_published()` for the broadened definition.
        """
        stmt = (
            select(ArticleDraftModel)
            .where(
                and_(
                    ArticleDraftModel.account_id == account_id,
                    or_(
                        ArticleDraftModel.publish_status == "published",
                        ArticleDraftModel.status == "published",
                    ),
                )
            )
            .order_by(
                desc(ArticleDraftModel.published_at),
                desc(ArticleDraftModel.created_at),
                desc(ArticleDraftModel.id),
            )
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)


memory_service = MemoryService()


def serialize_memory(memory: ArticleMemoryModel) -> dict[str, Any]:
    """Serialize an `ArticleMemoryModel` into the response shape expected by
    the frontend `ContentMemory` interface.

    Centralised here so routes stay thin; we use plain dicts rather than the
    Pydantic schema to avoid alias gymnastics with `metadata`/`metadata_json`.
    """
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    return {
        "id": memory.id,
        "account_id": memory.account_id,
        "source_draft_id": memory.source_draft_id,
        "source_task_id": memory.source_task_id,
        "article_id": memory.article_id,
        "title": memory.title,
        "summary": memory.summary,
        "content_excerpt": memory.content_excerpt,
        "tags": memory.tags or [],
        "keywords": memory.keywords or [],
        "metadata": memory.metadata_json or {},
        "published_at": _iso(memory.published_at),
        "created_at": _iso(memory.created_at),
        "updated_at": _iso(memory.updated_at),
    }
