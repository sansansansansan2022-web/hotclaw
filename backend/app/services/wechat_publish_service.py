"""WeChat publish service.

【微信发布服务】
- 发布草稿到微信公众号
- 查询发布状态
"""

import httpx

from app.core.logger import get_logger
from app.services.wechat_token_service import wechat_token_service, WeChatTokenError
from app.services.wechat_media_service import wechat_media_service, WeChatMediaError
from app.services.wechat_draft_service import wechat_draft_service, WeChatDraftError

logger = get_logger(__name__)


class WeChatPublishError(Exception):
    """WeChat publish related errors."""
    pass


class WeChatPublishService:
    """
    WeChat official account publish service.

    Handles the full publish flow:
    1. Replace external images with WeChat CDN URLs
    2. Upload thumb/cover image
    3. Create draft in WeChat
    4. Publish draft (freepublish/submit)
    """

    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"

    async def publish_article(
        self,
        app_id: str,
        app_secret: str,
        title: str,
        author: str | None,
        digest: str | None,
        content_html: str,
        thumb_media_id: str | None = None,
        need_open_comment: bool = True,
        only_fans_can_comment: bool = False
    ) -> dict:
        """
        Full publish flow: upload images -> create draft -> publish.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            title: Article title
            author: Article author
            digest: Article summary
            content_html: Article HTML content
            thumb_media_id: Cover image media_id (optional)
            need_open_comment: Enable comments
            only_fans_can_comment: Only fans can comment

        Returns:
            dict with publish result:
            {
                "success": bool,
                "media_id": str,
                "publish_id": str,
                "msg_id": str,
                "url": str (if published)
            }

        Raises:
            WeChatPublishError: When publish fails
        """
        try:
            # Step 1: Replace external images with WeChat CDN URLs
            logger.info("wechat_publish_replace_images", app_id=app_id)
            processed_content = await wechat_media_service.replace_content_images(
                app_id, app_secret, content_html
            )

            # Step 2: Upload thumb image if not provided
            if not thumb_media_id:
                # If no thumb, use a placeholder - we need at least empty string
                thumb_media_id = ""
                logger.warning(
                    "wechat_publish_no_thumb",
                    app_id=app_id,
                    message="No thumb_media_id provided, article will be created without cover"
                )

            # Step 3: Create draft in WeChat
            logger.info("wechat_publish_create_draft", app_id=app_id)
            media_id = await wechat_draft_service.create_draft(
                app_id=app_id,
                app_secret=app_secret,
                title=title,
                author=author,
                digest=digest,
                content=processed_content,
                content_source_url=None,
                thumb_media_id=thumb_media_id,
                need_open_comment=need_open_comment,
                only_fans_can_comment=only_fans_can_comment
            )

            # Step 4: Publish the draft (official free publish API)
            logger.info("wechat_publish_submit", app_id=app_id)
            publish_result = await self.free_publish(app_id, app_secret, media_id)

            result = {
                "success": True,
                "media_id": media_id,
                "publish_id": publish_result.get("publish_id"),
                "msg_id": publish_result.get("msg_id"),
                "url": publish_result.get("url"),
                "article_id": publish_result.get("articleidx"),
            }

            logger.info(
                "wechat_publish_success",
                app_id=app_id,
                media_id=media_id,
                publish_id=publish_result.get("publish_id")
            )

            return result

        except WeChatTokenError as e:
            logger.error("wechat_publish_token_error", app_id=app_id, error=str(e))
            raise WeChatPublishError(f"Token error: {e}")
        except WeChatMediaError as e:
            logger.error("wechat_publish_media_error", app_id=app_id, error=str(e))
            raise WeChatPublishError(f"Media upload error: {e}")
        except WeChatDraftError as e:
            logger.error("wechat_publish_draft_error", app_id=app_id, error=str(e))
            raise WeChatPublishError(f"Draft error: {e}")
        except WeChatPublishError:
            raise
        except Exception as e:
            logger.error("wechat_publish_error", app_id=app_id, error=str(e))
            raise WeChatPublishError(f"Publish error: {e}")

    async def _submit_draft(
        self,
        app_id: str,
        app_secret: str,
        media_id: str
    ) -> dict:
        """
        Submit draft for publishing.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            media_id: Draft media_id to submit

        Returns:
            dict with publish result including msg_id
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/media/submit_preview"
            params = {"access_token": access_token}

            # For direct publish, we use mass_send or free_publish
            # Note: mass_preview returns a msg_id for preview
            # For actual publish, we use the free_publish API

            payload = {"media_id": media_id}

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "submit failed")
                logger.error(
                    "wechat_submit_failed",
                    app_id=app_id,
                    media_id=media_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatPublishError(f"Failed to submit: {error_msg}")

            return data

        except httpx.TimeoutException:
            logger.error("wechat_submit_timeout", app_id=app_id)
            raise WeChatPublishError("Submit timeout")
        except WeChatTokenError:
            raise
        except WeChatPublishError:
            raise
        except Exception as e:
            logger.error("wechat_submit_error", app_id=app_id, error=str(e))
            raise WeChatPublishError(f"Submit error: {e}")

    async def free_publish(
        self,
        app_id: str,
        app_secret: str,
        media_id: str
    ) -> dict:
        """
        Free publish a draft article (directly publish to official account).

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            media_id: Draft media_id to publish

        Returns:
            dict with publish result
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/freepublish/submit"
            params = {"access_token": access_token}

            payload = {"media_id": media_id}

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "free publish failed")
                logger.error(
                    "wechat_free_publish_failed",
                    app_id=app_id,
                    media_id=media_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatPublishError(f"Failed to free publish: {error_msg}")

            logger.info(
                "wechat_free_publish_submitted",
                app_id=app_id,
                media_id=media_id,
                publish_id=data.get("publish_id")
            )

            return {
                "success": True,
                "publish_id": data.get("publish_id"),
                "msg_id": data.get("msg_id")
            }

        except httpx.TimeoutException:
            logger.error("wechat_free_publish_timeout", app_id=app_id)
            raise WeChatPublishError("Free publish timeout")
        except WeChatTokenError:
            raise
        except Exception as e:
            logger.error("wechat_free_publish_error", app_id=app_id, error=str(e))
            raise WeChatPublishError(f"Free publish error: {e}")

    async def get_publish_status(
        self,
        app_id: str,
        app_secret: str,
        publish_id: str
    ) -> dict:
        """
        Query publish status.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            publish_id: Publish job ID from free_publish

        Returns:
            dict with status info:
            {
                "status": "pending" | "success" | "failed",
                "article_id": str (if published),
                "msg_id": str
            }
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/freepublish/getpubqueuejob"
            params = {"access_token": access_token}

            payload = {"publish_id": publish_id}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, params=params, json=payload)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "get status failed")
                logger.error(
                    "wechat_publish_status_failed",
                    app_id=app_id,
                    publish_id=publish_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatPublishError(f"Failed to get status: {error_msg}")

            # Parse status
            status_map = {
                0: "pending",
                1: "pending",
                2: "success",
                3: "failed",
                4: "failed"
            }
            status = status_map.get(data.get("publish_status", 0), "pending")

            result = {
                "status": status,
                "article_id": data.get("article_id"),
                "msg_id": data.get("msg_id"),
                "publish_status": data.get("publish_status")
            }

            logger.info(
                "wechat_publish_status",
                app_id=app_id,
                publish_id=publish_id,
                status=status
            )

            return result

        except httpx.TimeoutException:
            logger.error("wechat_publish_status_timeout", app_id=app_id)
            raise WeChatPublishError("Get publish status timeout")
        except WeChatTokenError:
            raise
        except Exception as e:
            logger.error("wechat_publish_status_error", app_id=app_id, error=str(e))
            raise WeChatPublishError(f"Get publish status error: {e}")


wechat_publish_service = WeChatPublishService()
