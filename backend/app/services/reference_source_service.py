"""Service layer for account reference sources."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotFoundError
from app.core.logger import get_logger
from app.models.tables import AccountModel, ReferenceSourceModel

logger = get_logger(__name__)

VALID_SOURCE_TYPES = {"wechat_account", "article_url", "pasted_article"}
VALID_SYNC_STATUSES = {"pending", "synced", "failed", "manual_only"}


class ReferenceSourceService:
    """Manage reference sources for a single account."""

    async def list_sources(self, account_id: str, db: AsyncSession) -> list[ReferenceSourceModel]:
        await self._get_account(account_id, db)
        stmt = (
            select(ReferenceSourceModel)
            .where(ReferenceSourceModel.account_id == account_id)
            .order_by(desc(ReferenceSourceModel.updated_at), desc(ReferenceSourceModel.id))
        )
        result = await db.execute(stmt)
        sources = list(result.scalars().all())
        logger.info("reference_sources_listed", account_id=account_id, source_count=len(sources))
        return sources

    async def create_source(
        self, account_id: str, data: dict, db: AsyncSession
    ) -> ReferenceSourceModel:
        await self._get_account(account_id, db)

        source_type = str(data.get("source_type") or "").strip()
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"unsupported source_type: {source_type}")

        source_value = str(data.get("source_value") or "").strip()
        if not source_value:
            raise ValueError("source_value is required")

        sync_status = self._default_sync_status(source_type)
        article_count = 1 if source_type == "pasted_article" else 0
        metadata_json = self._build_initial_metadata(source_type, source_value)

        source = ReferenceSourceModel(
            account_id=account_id,
            source_type=source_type,
            name=(data.get("name") or self._derive_name(source_type, source_value)).strip(),
            source_value=source_value,
            notes=(data.get("notes") or None),
            is_enabled=bool(data.get("is_enabled", True)),
            sync_status=sync_status,
            last_synced_at=datetime.now(timezone.utc) if source_type == "pasted_article" else None,
            article_count=article_count,
            latest_error_message=None,
            metadata_json=metadata_json,
        )
        db.add(source)
        await db.flush()
        logger.info(
            "reference_source_created",
            account_id=account_id,
            source_id=source.id,
            source_type=source.source_type,
            sync_status=source.sync_status,
        )
        return source

    async def update_source(
        self, account_id: str, source_id: int, data: dict, db: AsyncSession
    ) -> ReferenceSourceModel:
        source = await self.get_source(account_id, source_id, db)
        if "name" in data and data["name"] is not None:
            source.name = str(data["name"]).strip() or source.name
        if "notes" in data:
            source.notes = data["notes"] or None
        if "is_enabled" in data and data["is_enabled"] is not None:
            source.is_enabled = bool(data["is_enabled"])

        db.add(source)
        await db.flush()
        logger.info(
            "reference_source_updated",
            account_id=account_id,
            source_id=source_id,
            fields=sorted(data.keys()),
            is_enabled=source.is_enabled,
        )
        return source

    async def sync_source(
        self, account_id: str, source_id: int, db: AsyncSession
    ) -> tuple[ReferenceSourceModel, str]:
        source = await self.get_source(account_id, source_id, db)

        if source.source_type == "article_url":
            metadata_json, error_message = await self._fetch_article_url_source(source.source_value)
            if error_message:
                source.sync_status = "failed"
                source.latest_error_message = error_message
                message = "Reference source sync failed. The source is still saved for manual use."
            else:
                source.sync_status = "synced"
                source.last_synced_at = datetime.now(timezone.utc)
                source.article_count = max(source.article_count, 1)
                source.latest_error_message = None
                source.metadata_json = {
                    **(source.metadata_json or {}),
                    **metadata_json,
                }
                message = "Reference source synced successfully."
        elif source.source_type == "pasted_article":
            source.sync_status = "manual_only"
            source.last_synced_at = datetime.now(timezone.utc)
            source.article_count = max(source.article_count, 1)
            source.latest_error_message = None
            source.metadata_json = {
                **(source.metadata_json or {}),
                "content_length": len(source.source_value),
            }
            message = "Pasted article sources are stored as manual-only references."
        else:
            source.sync_status = "manual_only"
            source.latest_error_message = "WeChat account syncing is not available yet. Source kept for manual reference."
            message = "WeChat account sources are currently tracked as manual-only references."

        db.add(source)
        await db.flush()
        logger.info(
            "reference_source_synced",
            account_id=account_id,
            source_id=source_id,
            source_type=source.source_type,
            sync_status=source.sync_status,
        )
        return source, message

    async def get_source(
        self, account_id: str, source_id: int, db: AsyncSession
    ) -> ReferenceSourceModel:
        await self._get_account(account_id, db)
        stmt = select(ReferenceSourceModel).where(
            ReferenceSourceModel.account_id == account_id,
            ReferenceSourceModel.id == source_id,
        )
        result = await db.execute(stmt)
        source = result.scalar_one_or_none()
        if source is None:
            raise ValueError(f"reference source {source_id} was not found for account {account_id}")
        return source

    async def _get_account(self, account_id: str, db: AsyncSession) -> AccountModel:
        stmt = select(AccountModel).where(AccountModel.id == account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    def _default_sync_status(self, source_type: str) -> str:
        if source_type == "pasted_article":
            return "manual_only"
        if source_type == "wechat_account":
            return "pending"
        return "pending"

    def _derive_name(self, source_type: str, source_value: str) -> str:
        if source_type == "article_url":
            parsed = urlparse(source_value)
            return parsed.netloc or "Article URL Source"
        if source_type == "wechat_account":
            return source_value[:120]
        return (source_value[:60] + "...") if len(source_value) > 60 else source_value

    def _build_initial_metadata(self, source_type: str, source_value: str) -> dict | None:
        if source_type == "article_url":
            parsed = urlparse(source_value)
            return {"url_host": parsed.netloc or None}
        if source_type == "pasted_article":
            return {
                "content_length": len(source_value),
                "preview": source_value[:280],
            }
        return None

    async def _fetch_article_url_source(self, source_value: str) -> tuple[dict, str | None]:
        return await asyncio.to_thread(self._fetch_article_url_source_sync, source_value)

    def _fetch_article_url_source_sync(self, source_value: str) -> tuple[dict, str | None]:
        try:
            request = Request(
                source_value,
                headers={
                    "User-Agent": "HotClawReferenceSource/1.0",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            with urlopen(request, timeout=8) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            return {}, f"Could not fetch {source_value}. Suggest manual review or pasted article fallback. ({exc})"

        decoded = self._decode_bytes(raw)
        if not decoded:
            return {}, f"Fetched {source_value} but could not decode the article body."

        text = self._html_to_text(decoded)
        if len(text) < 200:
            return {}, f"Fetched {source_value} but extracted too little readable text."

        parsed = urlparse(source_value)
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", decoded)
        return (
            {
                "url_host": parsed.netloc or None,
                "resolved_title": unescape(title_match.group(1).strip()) if title_match else None,
                "content_length": len(text),
                "preview": text[:280],
            },
            None,
        )

    def _decode_bytes(self, raw: bytes) -> str:
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")

    def _html_to_text(self, html_content: str) -> str:
        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_content)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", cleaned)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()


reference_source_service = ReferenceSourceService()
