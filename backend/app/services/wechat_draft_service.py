"""WeChat draft management service.

【微信草稿服务】
- 创建微信草稿
- 更新微信草稿
- 删除微信草稿
"""

import httpx
import json

from app.core.logger import get_logger
from app.services.wechat_token_service import wechat_token_service, WeChatTokenError

logger = get_logger(__name__)


class WeChatDraftError(Exception):
    """WeChat draft related errors."""
    pass


class WeChatDraftService:
    """
    WeChat official account draft management.

    Uses WeChat material/news API for draft management.
    """

    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"

    async def create_draft(
        self,
        app_id: str,
        app_secret: str,
        title: str,
        author: str | None,
        digest: str | None,
        content: str,
        content_source_url: str | None,
        thumb_media_id: str | None,
        need_open_comment: bool = True,
        only_fans_can_comment: bool = False
    ) -> str:
        """
        Create a new draft article in WeChat.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            title: Article title
            author: Article author (optional)
            digest: Article summary/digest (optional)
            content: Article HTML content
            content_source_url: Original article URL (optional)
            thumb_media_id: Cover image media_id
            need_open_comment: Enable comments
            only_fans_can_comment: Only fans can comment

        Returns:
            media_id of created draft article

        Raises:
            WeChatDraftError: When draft creation fails
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/draft/add"
            params = {"access_token": access_token}

            # Build articles list (news item)
            articles = [{
                "title": title,
                "author": author or "",
                "digest": digest or title[:54],  # digest max 54 chars
                "content": content,
                "content_source_url": content_source_url or "",
                "thumb_media_id": thumb_media_id or "",
                "need_open_comment": 1 if need_open_comment else 0,
                "only_fans_can_comment": 1 if only_fans_can_comment else 0,
            }]

            payload = {"articles": articles}

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "create draft failed")
                logger.error(
                    "wechat_draft_create_failed",
                    app_id=app_id,
                    title=title,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatDraftError(f"Failed to create draft: {error_msg}")

            media_id = data.get("media_id")
            logger.info(
                "wechat_draft_created",
                app_id=app_id,
                media_id=media_id,
                title=title
            )

            return media_id

        except httpx.TimeoutException:
            logger.error("wechat_draft_create_timeout", app_id=app_id)
            raise WeChatDraftError("Draft creation timeout")
        except WeChatTokenError:
            raise
        except WeChatDraftError:
            raise
        except Exception as e:
            logger.error("wechat_draft_create_error", app_id=app_id, error=str(e))
            raise WeChatDraftError(f"Draft creation error: {e}")

    async def update_draft(
        self,
        app_id: str,
        app_secret: str,
        media_id: str,
        title: str,
        author: str | None,
        digest: str | None,
        content: str,
        content_source_url: str | None,
        thumb_media_id: str | None,
        index: int = 0,
        need_open_comment: bool = True,
        only_fans_can_comment: bool = False
    ) -> bool:
        """
        Update an existing draft article.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            media_id: Draft media_id to update
            title: Article title
            author: Article author
            digest: Article summary
            content: Article HTML content
            content_source_url: Original article URL
            thumb_media_id: Cover image media_id
            index: Article index in the news (0 for first article)
            need_open_comment: Enable comments
            only_fans_can_comment: Only fans can comment

        Returns:
            True if successful

        Raises:
            WeChatDraftError: When update fails
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/draft/update"
            params = {"access_token": access_token}

            articles = [{
                "title": title,
                "author": author or "",
                "digest": digest or title[:54],
                "content": content,
                "content_source_url": content_source_url or "",
                "thumb_media_id": thumb_media_id or "",
                "need_open_comment": 1 if need_open_comment else 0,
                "only_fans_can_comment": 1 if only_fans_can_comment else 0,
            }]

            payload = {
                "media_id": media_id,
                "index": index,
                "articles": articles
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "update draft failed")
                logger.error(
                    "wechat_draft_update_failed",
                    app_id=app_id,
                    media_id=media_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatDraftError(f"Failed to update draft: {error_msg}")

            logger.info(
                "wechat_draft_updated",
                app_id=app_id,
                media_id=media_id
            )

            return True

        except httpx.TimeoutException:
            logger.error("wechat_draft_update_timeout", app_id=app_id)
            raise WeChatDraftError("Draft update timeout")
        except WeChatTokenError:
            raise
        except WeChatDraftError:
            raise
        except Exception as e:
            logger.error("wechat_draft_update_error", app_id=app_id, error=str(e))
            raise WeChatDraftError(f"Draft update error: {e}")

    async def delete_draft(
        self,
        app_id: str,
        app_secret: str,
        media_id: str
    ) -> bool:
        """
        Delete a draft article.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            media_id: Draft media_id to delete

        Returns:
            True if successful

        Raises:
            WeChatDraftError: When delete fails
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/draft/delete"
            params = {"access_token": access_token}

            payload = {"media_id": media_id}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "delete draft failed")
                logger.error(
                    "wechat_draft_delete_failed",
                    app_id=app_id,
                    media_id=media_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatDraftError(f"Failed to delete draft: {error_msg}")

            logger.info(
                "wechat_draft_deleted",
                app_id=app_id,
                media_id=media_id
            )

            return True

        except httpx.TimeoutException:
            logger.error("wechat_draft_delete_timeout", app_id=app_id)
            raise WeChatDraftError("Draft delete timeout")
        except WeChatTokenError:
            raise
        except WeChatDraftError:
            raise
        except Exception as e:
            logger.error("wechat_draft_delete_error", app_id=app_id, error=str(e))
            raise WeChatDraftError(f"Draft delete error: {e}")

    async def get_draft(
        self,
        app_id: str,
        app_secret: str,
        media_id: str
    ) -> dict | None:
        """
        Get draft article details.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            media_id: Draft media_id

        Returns:
            Draft details dict or None

        Raises:
            WeChatDraftError: When fetch fails
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/draft/get"
            params = {"access_token": access_token}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "get draft failed")
                logger.error(
                    "wechat_draft_get_failed",
                    app_id=app_id,
                    media_id=media_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatDraftError(f"Failed to get draft: {error_msg}")

            return data.get("news_item")

        except httpx.TimeoutException:
            logger.error("wechat_draft_get_timeout", app_id=app_id)
            raise WeChatDraftError("Draft get timeout")
        except WeChatTokenError:
            raise
        except WeChatDraftError:
            raise
        except Exception as e:
            logger.error("wechat_draft_get_error", app_id=app_id, error=str(e))
            raise WeChatDraftError(f"Draft get error: {e}")


wechat_draft_service = WeChatDraftService()
