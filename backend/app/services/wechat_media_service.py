"""WeChat media upload service.

【微信媒体上传服务】
- 上传图文正文中的图片
- 上传封面缩略图
"""

import httpx
import re
import base64
import hashlib
from io import BytesIO

from app.core.logger import get_logger
from app.services.wechat_token_service import wechat_token_service, WeChatTokenError

logger = get_logger(__name__)


class WeChatMediaError(Exception):
    """WeChat media upload related errors."""
    pass


class WeChatMediaService:
    """
    WeChat media upload service.

    Handles:
    - Content image upload (for article body)
    - Thumb image upload (for article cover)
    """

    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"

    # Supported image formats for upload
    SUPPORTED_IMAGE_TYPES = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}

    async def upload_content_image(
        self,
        app_id: str,
        app_secret: str,
        image_data: bytes,
        filename: str = "image.png"
    ) -> str:
        """
        Upload image to WeChat for article content.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            image_data: Raw image bytes
            filename: Filename for the image

        Returns:
            URL of uploaded image

        Raises:
            WeChatMediaError: When upload fails
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/media/upload"
            params = {"access_token": access_token, "type": "image"}

            # Prepare multipart form
            files = {
                "media": (filename, BytesIO(image_data), f"image/{self._get_image_type(filename)}")
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, files=files)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "upload failed")
                logger.error(
                    "wechat_image_upload_failed",
                    app_id=app_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatMediaError(f"Image upload failed: {error_msg}")

            # WeChat returns URL for permanent images
            image_url = data.get("url") or data.get("media_id")
            logger.info(
                "wechat_image_uploaded",
                app_id=app_id,
                media_id=data.get("media_id")
            )

            return image_url

        except httpx.TimeoutException:
            logger.error("wechat_image_upload_timeout", app_id=app_id)
            raise WeChatMediaError("Image upload timeout")
        except WeChatTokenError:
            raise
        except WeChatMediaError:
            raise
        except Exception as e:
            logger.error("wechat_image_upload_error", app_id=app_id, error=str(e))
            raise WeChatMediaError(f"Image upload error: {e}")

    async def upload_thumb_image(
        self,
        app_id: str,
        app_secret: str,
        image_data: bytes,
        filename: str = "thumb.png"
    ) -> str:
        """
        Upload thumb/cover image to WeChat.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            image_data: Raw image bytes
            filename: Filename for the image

        Returns:
            media_id of uploaded thumb image

        Raises:
            WeChatMediaError: When upload fails
        """
        try:
            access_token = await wechat_token_service.get_access_token(app_id, app_secret)

            url = f"{self.WECHAT_API_BASE}/media/upload"
            params = {"access_token": access_token, "type": "thumb"}

            files = {
                "media": (filename, BytesIO(image_data), f"image/{self._get_image_type(filename)}")
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, files=files)
                data = response.json()

            if data.get("errcode") and data["errcode"] != 0:
                error_msg = data.get("errmsg", "upload failed")
                logger.error(
                    "wechat_thumb_upload_failed",
                    app_id=app_id,
                    errcode=data["errcode"],
                    errmsg=error_msg
                )
                raise WeChatMediaError(f"Thumb upload failed: {error_msg}")

            media_id = data.get("thumb_media_id")
            logger.info(
                "wechat_thumb_uploaded",
                app_id=app_id,
                thumb_media_id=media_id
            )

            return media_id

        except httpx.TimeoutException:
            logger.error("wechat_thumb_upload_timeout", app_id=app_id)
            raise WeChatMediaError("Thumb upload timeout")
        except WeChatTokenError:
            raise
        except WeChatMediaError:
            raise
        except Exception as e:
            logger.error("wechat_thumb_upload_error", app_id=app_id, error=str(e))
            raise WeChatMediaError(f"Thumb upload error: {e}")

    async def replace_content_images(
        self,
        app_id: str,
        app_secret: str,
        content_html: str
    ) -> str:
        """
        Replace external image URLs in HTML content with WeChat URLs.

        Downloads external images and re-uploads to WeChat.

        Args:
            app_id: WeChat App ID
            app_secret: WeChat App Secret
            content_html: HTML content with external image URLs

        Returns:
            HTML content with WeChat image URLs
        """
        # Find all external image URLs in the content
        image_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>')
        matches = image_pattern.findall(content_html)

        if not matches:
            logger.info("wechat_no_external_images", app_id=app_id)
            return content_html

        result_html = content_html
        upload_count = 0

        for img_url in matches:
            # Skip WeChat CDN images and data URLs
            if img_url.startswith("http://mmbiz") or img_url.startswith("https://mmbiz"):
                continue
            if img_url.startswith("data:"):
                continue

            try:
                # Download image
                async with httpx.AsyncClient(timeout=30.0) as client:
                    img_response = await client.get(img_url)
                    img_response.raise_for_status()
                    image_data = img_response.content

                # Upload to WeChat
                wechat_url = await self.upload_content_image(
                    app_id, app_secret, image_data
                )

                # Replace URL in HTML
                result_html = result_html.replace(img_url, wechat_url)
                upload_count += 1

                logger.info(
                    "wechat_image_replaced",
                    app_id=app_id,
                    original_url=img_url,
                    wechat_url=wechat_url
                )

            except Exception as e:
                # Log error but don't fail - keep original URL
                logger.warning(
                    "wechat_image_replace_failed",
                    app_id=app_id,
                    url=img_url,
                    error=str(e)
                )

        logger.info(
            "wechat_content_images_processed",
            app_id=app_id,
            upload_count=upload_count
        )

        return result_html

    def _get_image_type(self, filename: str) -> str:
        """Get image type from filename."""
        ext = filename.lower().split(".")[-1] if "." in filename else "png"
        return ext if ext in self.SUPPORTED_IMAGE_TYPES else "png"


wechat_media_service = WeChatMediaService()
