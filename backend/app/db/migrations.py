"""One-off and idempotent data migrations run at application startup."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import AccountModel

logger = get_logger(__name__)


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
