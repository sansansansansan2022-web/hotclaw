"""WeChat API token management service.

【微信 Access Token 管理】
- 基于 app_id / app_secret 获取 access_token
- 支持缓存和过期自动刷新
- 线程安全
"""

import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

# Token cache in module level (simple, works for single instance)
_token_cache: dict[str, dict] = {}


class WeChatTokenError(Exception):
    """WeChat token related errors."""
    pass


class WeChatTokenService:
    """
    WeChat access_token management service.

    Token 有效期为 7200 秒（2小时），本服务会提前刷新。
    """

    # WeChat API base URL
    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"

    # Token cache duration (refresh 5 minutes before expiry)
    TOKEN_CACHE_DURATION = timedelta(hours=2)
    TOKEN_REFRESH_BEFORE = timedelta(minutes=5)

    async def get_access_token(
        self,
        app_id: str,
        app_secret: str,
        force_refresh: bool = False
    ) -> str:
        """
        Get valid access_token for the app.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            force_refresh: Force refresh token even if cached

        Returns:
            Valid access_token string

        Raises:
            WeChatTokenError: When token fetch fails
        """
        cache_key = f"{app_id}"

        # Check cache first
        if not force_refresh and cache_key in _token_cache:
            cached = _token_cache[cache_key]
            expires_at = cached.get("expires_at")
            if expires_at and datetime.now(timezone.utc) < expires_at - self.TOKEN_REFRESH_BEFORE:
                logger.info("wechat_token_cached", app_id=app_id)
                return cached["access_token"]

        # Fetch new token
        token, expires_in = await self._fetch_access_token(app_id, app_secret)

        # Cache token
        _token_cache[cache_key] = {
            "access_token": token,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        }

        logger.info(
            "wechat_token_refreshed",
            app_id=app_id,
            expires_in=expires_in
        )

        return token

    async def _fetch_access_token(
        self,
        app_id: str,
        app_secret: str
    ) -> tuple[str, int]:
        """
        Fetch access_token from WeChat API.

        Returns:
            Tuple of (access_token, expires_in seconds)

        Raises:
            WeChatTokenError: When API call fails
        """
        url = f"{self.WECHAT_API_BASE}/token"
        params = {
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "unknown error")
                logger.error(
                    "wechat_token_fetch_failed",
                    app_id=app_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatTokenError(
                    f"Failed to get access_token: {error_msg} (code: {data['errcode']})"
                )

            return data["access_token"], data["expires_in"]

        except httpx.TimeoutException:
            logger.error("wechat_token_timeout", app_id=app_id)
            raise WeChatTokenError("Access token request timeout")
        except httpx.HTTPError as e:
            logger.error("wechat_token_http_error", app_id=app_id, error=str(e))
            raise WeChatTokenError(f"Access token request failed: {e}")
        except (KeyError, ValueError) as e:
            logger.error("wechat_token_parse_error", app_id=app_id, error=str(e))
            raise WeChatTokenError(f"Failed to parse token response: {e}")

    async def test_connection(
        self,
        app_id: str,
        app_secret: str
    ) -> tuple[bool, str]:
        """
        Test WeChat API connection.

        Returns:
            Tuple of (success, message)
        """
        try:
            await self._fetch_access_token(app_id, app_secret)
            return True, "Connection successful"
        except WeChatTokenError as e:
            return False, str(e)

    def clear_cache(self, app_id: str):
        """Clear token cache for an app."""
        cache_key = f"{app_id}"
        if cache_key in _token_cache:
            del _token_cache[cache_key]
            logger.info("wechat_token_cache_cleared", app_id=app_id)


wechat_token_service = WeChatTokenService()
