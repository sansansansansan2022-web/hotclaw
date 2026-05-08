"""One-off and idempotent data migrations run at application startup."""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.logger import get_logger
from app.models.tables import AccountModel

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DDL-level column additions (SQLite does not support ALTER TABLE ADD COLUMN
# IF NOT EXISTS before SQLite 3.37; we probe via PRAGMA and add if missing).
# ---------------------------------------------------------------------------

_ACCOUNTS_NEW_COLUMNS: list[tuple[str, str]] = [
    # (column_name, sqlite_type_definition)
    # Legacy column that may be missing in fresh DBs created before this schema.
    ("profile_json", "TEXT"),
    ("base_profile_json", "TEXT"),
    ("evolved_profile_json", "TEXT"),
    ("style_profile_json", "TEXT"),
    ("profile_version", "INTEGER DEFAULT 1"),
    ("last_evolved_at", "DATETIME"),
]


async def ensure_accounts_columns(engine: AsyncEngine) -> None:
    """Idempotent: add three-layer profile columns to `accounts` if missing."""
    async with engine.begin() as conn:
        # PRAGMA table_info returns one row per column.
        result = await conn.execute(text("PRAGMA table_info(accounts)"))
        existing = {row[1] for row in result.fetchall()}  # index 1 = name

        added: list[str] = []
        for col_name, col_def in _ACCOUNTS_NEW_COLUMNS:
            if col_name not in existing:
                await conn.execute(
                    text(f"ALTER TABLE accounts ADD COLUMN {col_name} {col_def}")
                )
                added.append(col_name)

        if added:
            logger.info("accounts_columns_added", columns=added)
        else:
            logger.debug("accounts_columns_already_exist")


# ---------------------------------------------------------------------------
# Data migrations
# ---------------------------------------------------------------------------


async def migrate_legacy_profile_json(db: AsyncSession) -> None:
    """Idempotent: copy profile_json to base_profile_json when base is empty."""
    stmt = select(AccountModel).where(
        AccountModel.base_profile_json.is_(None),
        AccountModel.profile_json.isnot(None),
    )
    result = await db.execute(stmt)
    accounts = list(result.scalars().all())
    for account in accounts:
        account.base_profile_json = account.profile_json
    if accounts:
        await db.flush()
        logger.info("profile_json_migrated_to_base", count=len(accounts))
