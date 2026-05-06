"""WeChat API token management service."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logger import get_logger
from app.db.session import get_db_context
from app.models.wechat_config import WeChatConfigModel

logger = get_logger(__name__)


class WeChatTokenError(Exception):
    """WeChat token related errors."""


_refresh_locks: dict[int, asyncio.Lock] = {}


class WeChatTokenService:
    """Fetch, cache, refresh, and test WeChat Official Account access tokens."""

    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
    REFRESH_BUFFER_SECONDS = 300

    async def get_valid_access_token(
        self,
        config_id: int | str,
        db: AsyncSession | None = None,
    ) -> str:
        """Return a valid token from database cache, refreshing when required."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.get_valid_access_token(config_id, managed_db)

        config = await self._get_config(config_id, db)
        if not config:
            raise WeChatTokenError(f"WeChat config {config_id} not found")

        if self._is_token_valid(config):
            return config.access_token or ""

        return await self.refresh_access_token(config_id, db)

    async def refresh_access_token(
        self,
        config_id: int | str,
        db: AsyncSession | None = None,
    ) -> str:
        """Force refresh access_token and persist it back to the config row."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.refresh_access_token(config_id, managed_db)

        config = await self._get_config(config_id, db)
        if not config:
            raise WeChatTokenError(f"WeChat config {config_id} not found")

        if not config.app_id or not config.app_secret:
            raise WeChatTokenError(f"WeChat config {config.account_id} is missing app_id or app_secret")

        lock = _refresh_locks.setdefault(config.id, asyncio.Lock())
        async with lock:
            await db.refresh(config)
            if self._is_token_valid(config):
                return config.access_token or ""

            token_data = await self._fetch_access_token(config.app_id, config.app_secret)
            expires_in = int(token_data.get("expires_in", 7200))
            now = datetime.now(timezone.utc)

            config.access_token = token_data["access_token"]
            config.access_token_expires_at = now + timedelta(seconds=expires_in)
            config.test_status = "success"
            config.test_message = None
            config.last_sync_at = now
            db.add(config)
            await db.flush()

            logger.info(
                "wechat_token_refreshed",
                config_id=config.id,
                account_id=config.account_id,
                expires_in=expires_in,
            )
            return config.access_token

    async def test_connection(
        self,
        config_id: int | str,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Test persisted config by refreshing token and hitting a lightweight WeChat endpoint."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.test_connection(config_id, managed_db)

        config = await self._get_config(config_id, db)
        if not config:
            raise WeChatTokenError(f"WeChat config {config_id} not found")

        tested_at = datetime.now(timezone.utc)
        try:
            token = await self.refresh_access_token(config.id, db)
            callback_result = await self._call_json(
                method="GET",
                endpoint="/getcallbackip",
                access_token=token,
            )
            ip_count = len(callback_result.get("ip_list", [])) if isinstance(callback_result, dict) else 0

            config.test_status = "success"
            config.test_message = None
            config.last_sync_at = tested_at
            db.add(config)
            await db.flush()

            return {
                "success": True,
                "message": f"Connection successful, callback IP entries: {ip_count}",
                "tested_at": tested_at,
                "token_expires_at": config.access_token_expires_at,
            }
        except Exception as exc:
            config.test_status = "failed"
            config.test_message = str(exc)[:500]
            config.last_sync_at = tested_at
            db.add(config)
            await db.flush()
            logger.warning("wechat_connection_test_failed", config_id=config.id, error=str(exc))
            return {
                "success": False,
                "message": str(exc),
                "tested_at": tested_at,
                "token_expires_at": None,
            }

    async def test_credentials(self, app_id: str, app_secret: str) -> dict[str, Any]:
        """Test a raw App ID / App Secret pair without storing it."""

        tested_at = datetime.now(timezone.utc)
        try:
            token_data = await self._fetch_access_token(app_id, app_secret)
            token = token_data["access_token"]
            expires_in = int(token_data.get("expires_in", 7200))
            await self._call_json("GET", "/getcallbackip", access_token=token)
            return {
                "success": True,
                "message": "Connection successful",
                "tested_at": tested_at,
                "token_expires_at": tested_at + timedelta(seconds=expires_in),
            }
        except Exception as exc:
            logger.warning("wechat_credentials_test_failed", app_id=app_id, error=str(exc))
            return {
                "success": False,
                "message": str(exc),
                "tested_at": tested_at,
                "token_expires_at": None,
            }

    async def get_access_token(
        self,
        app_id: str,
        app_secret: str,
        force_refresh: bool = False,
    ) -> str:
        """Legacy compatibility helper for existing low-level services."""

        token_data = await self._fetch_access_token(app_id, app_secret) if force_refresh else await self._fetch_access_token(app_id, app_secret)
        return token_data["access_token"]

    async def clear_cache(self, app_id_or_config_id: str | int, db: AsyncSession | None = None) -> None:
        """Clear persisted token state for a config or app_id."""

        if db is None:
            async with get_db_context() as managed_db:
                await self.clear_cache(app_id_or_config_id, managed_db)
                return

        config = await self._get_config(app_id_or_config_id, db)
        if not config and isinstance(app_id_or_config_id, str):
            config = await self._get_config_by_app_id(app_id_or_config_id, db)

        if not config:
            return

        config.access_token = None
        config.access_token_expires_at = None
        db.add(config)
        await db.flush()
        logger.info("wechat_token_cache_cleared", config_id=config.id, account_id=config.account_id)

    async def _get_config(self, config_id: int | str, db: AsyncSession) -> WeChatConfigModel | None:
        if isinstance(config_id, str) and not config_id.isdigit():
            return await self._get_config_by_account_id(config_id, db)

        return await db.get(WeChatConfigModel, int(config_id))

    async def _get_config_by_account_id(self, account_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        result = await db.execute(select(WeChatConfigModel).where(WeChatConfigModel.account_id == account_id))
        return result.scalar_one_or_none()

    async def _get_config_by_app_id(self, app_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        result = await db.execute(select(WeChatConfigModel).where(WeChatConfigModel.app_id == app_id))
        return result.scalar_one_or_none()

    def _is_token_valid(self, config: WeChatConfigModel) -> bool:
        if not config.access_token or not config.access_token_expires_at:
            return False
        now = datetime.now(timezone.utc)
        expires_at = config.access_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > now + timedelta(seconds=self.REFRESH_BUFFER_SECONDS)

    async def _fetch_access_token(self, app_id: str, app_secret: str) -> dict[str, Any]:
        return await self._call_json(
            method="GET",
            endpoint="/token",
            params={
                "grant_type": "client_credential",
                "appid": app_id,
                "secret": app_secret,
            },
        )

    async def _call_json(
        self,
        method: str,
        endpoint: str,
        *,
        access_token: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        url = f"{self.WECHAT_API_BASE}{endpoint}"
        request_params = dict(params or {})
        if access_token:
            request_params["access_token"] = access_token

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, url, params=request_params, json=json_body)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise WeChatTokenError(f"WeChat request timeout for {endpoint}") from exc
        except httpx.HTTPStatusError as exc:
            raise WeChatTokenError(f"WeChat HTTP error for {endpoint}: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise WeChatTokenError(f"WeChat request failed for {endpoint}: {exc}") from exc
        except ValueError as exc:
            raise WeChatTokenError(f"Invalid JSON response from WeChat endpoint {endpoint}") from exc

        errcode = data.get("errcode")
        if errcode not in (None, 0):
            errmsg = data.get("errmsg", "unknown error")
            raise WeChatTokenError(f"WeChat API error {errcode}: {errmsg}")

        return data


wechat_token_service = WeChatTokenService()
