"""WeChat media upload and article image rewriting service."""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.session import get_db_context
from app.models.wechat_config import WeChatConfigModel
from app.services.wechat_token_service import wechat_token_service

logger = get_logger(__name__)


class WeChatMediaError(Exception):
    """WeChat media upload related errors."""


class WeChatMediaService:
    """Upload article images and rewrite HTML for WeChat compatibility."""

    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
    IMG_TAG_PATTERN = re.compile(r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'][^>]*>)', re.IGNORECASE)
    SUPPORTED_IMAGE_TYPES = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
    STATIC_CANDIDATE_ROOTS = (
        Path.cwd(),
        Path.cwd() / "backend",
        Path.cwd() / "frontend" / "public",
    )

    async def upload_article_image(
        self,
        account_id: str,
        image_bytes: bytes,
        filename: str,
        db: AsyncSession | None = None,
    ) -> str:
        """Upload an article body image and return the WeChat CDN URL."""

        return await self._upload_for_account(account_id, image_bytes, filename, endpoint="/media/uploadimg", db=db)

    async def upload_image_material(
        self,
        account_id: str,
        image_bytes: bytes,
        filename: str,
        db: AsyncSession | None = None,
    ) -> str:
        """Upload permanent image material and return the media_id."""

        return await self._upload_for_account(
            account_id,
            image_bytes,
            filename,
            endpoint="/material/add_material",
            params={"type": "image"},
            db=db,
        )

    async def rewrite_article_html_images(
        self,
        html: str,
        account_id: str | int,
        db: AsyncSession | None = None,
    ) -> tuple[str, str | None]:
        """Replace HTML image sources with WeChat URLs and derive a cover media_id.

        Supported image inputs:
        - `http://` or `https://` remote images
        - absolute local filesystem paths
        - relative filesystem paths under the repo/backend/frontend public directories
        - `/static/...`, `/public/...`, `/uploads/...` style rooted paths resolved locally
        - `data:image/...;base64,...` inline data URLs

        Not supported yet:
        - authenticated remote URLs requiring custom headers/cookies
        - SVG cover upload
        - CSS background images
        """

        if not html:
            return "", None

        if db is None:
            async with get_db_context() as managed_db:
                return await self.rewrite_article_html_images(html, account_id, managed_db)

        matches = list(self.IMG_TAG_PATTERN.finditer(html))
        if not matches:
            return html, None

        account_id_str = str(account_id)
        rewritten_html = html
        cover_media_id: str | None = None

        for match in matches:
            original_src = match.group(2).strip()
            if not original_src or self._is_wechat_host(original_src):
                continue

            try:
                image_bytes, filename = await self._resolve_image_source(original_src)
                if not image_bytes:
                    continue

                uploaded_url = await self.upload_article_image(account_id_str, image_bytes, filename, db)
                rewritten_html = rewritten_html.replace(original_src, uploaded_url, 1)

                if not cover_media_id:
                    try:
                        cover_media_id = await self.upload_image_material(account_id_str, image_bytes, filename, db)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "wechat_cover_upload_from_article_failed",
                            account_id=account_id_str,
                            source=original_src,
                            error=str(exc),
                        )

                logger.info(
                    "wechat_article_image_rewritten",
                    account_id=account_id_str,
                    original_src=original_src,
                    wechat_url=uploaded_url,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "wechat_article_image_rewrite_failed",
                    account_id=account_id_str,
                    source=original_src,
                    error=str(exc),
                )

        return rewritten_html, cover_media_id

    async def upload_content_image(
        self,
        app_id: str,
        app_secret: str,
        image_data: bytes,
        filename: str = "image.png",
    ) -> str:
        """Legacy compatibility wrapper for article image upload."""

        return await self._upload_by_credentials(app_id, app_secret, image_data, filename, endpoint="/media/uploadimg")

    async def upload_thumb_image(
        self,
        app_id: str,
        app_secret: str,
        image_data: bytes,
        filename: str = "thumb.png",
    ) -> str:
        """Legacy compatibility wrapper for image material upload."""

        return await self._upload_by_credentials(
            app_id,
            app_secret,
            image_data,
            filename,
            endpoint="/material/add_material",
            params={"type": "image"},
        )

    async def replace_content_images(self, app_id: str, app_secret: str, content_html: str) -> str:
        """Legacy compatibility wrapper used by older code paths."""

        if not content_html:
            return content_html

        rewritten_html = content_html
        for match in self.IMG_TAG_PATTERN.finditer(content_html):
            original_src = match.group(2).strip()
            if not original_src or self._is_wechat_host(original_src):
                continue
            try:
                image_bytes, filename = await self._resolve_image_source(original_src)
                new_url = await self._upload_by_credentials(app_id, app_secret, image_bytes, filename, "/media/uploadimg")
                rewritten_html = rewritten_html.replace(original_src, new_url, 1)
            except Exception as exc:  # noqa: BLE001
                logger.warning("wechat_replace_content_image_failed", app_id=app_id, source=original_src, error=str(exc))
        return rewritten_html

    async def _upload_for_account(
        self,
        account_id: str,
        image_bytes: bytes,
        filename: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        db: AsyncSession | None = None,
    ) -> str:
        if db is None:
            async with get_db_context() as managed_db:
                return await self._upload_for_account(account_id, image_bytes, filename, endpoint, params, managed_db)

        config = await self._get_config_for_account(account_id, db)
        if not config:
            raise WeChatMediaError(f"WeChat config not found for account {account_id}")

        token = await wechat_token_service.get_valid_access_token(config.id, db)
        return await self._upload_with_token(token, image_bytes, filename, endpoint, params=params)

    async def _upload_by_credentials(
        self,
        app_id: str,
        app_secret: str,
        image_bytes: bytes,
        filename: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        token = await wechat_token_service.get_access_token(app_id, app_secret)
        return await self._upload_with_token(token, image_bytes, filename, endpoint, params=params)

    async def _upload_with_token(
        self,
        access_token: str,
        image_bytes: bytes,
        filename: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> str:
        url = f"{self.WECHAT_API_BASE}{endpoint}"
        request_params = {"access_token": access_token, **(params or {})}
        content_type = self._guess_mime_type(filename)
        files = {"media": (filename, image_bytes, content_type)}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=request_params, files=files)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise WeChatMediaError(f"WeChat media upload timed out for {filename}") from exc
        except httpx.HTTPError as exc:
            raise WeChatMediaError(f"WeChat media upload failed for {filename}: {exc}") from exc
        except ValueError as exc:
            raise WeChatMediaError(f"Invalid WeChat media response for {filename}") from exc

        if data.get("errcode") not in (None, 0):
            raise WeChatMediaError(f"WeChat media API error {data.get('errcode')}: {data.get('errmsg')}")

        if endpoint == "/media/uploadimg":
            uploaded_url = data.get("url")
            if not uploaded_url:
                raise WeChatMediaError(f"WeChat image upload returned no URL for {filename}")
            return uploaded_url

        media_id = data.get("media_id")
        if not media_id:
            raise WeChatMediaError(f"WeChat material upload returned no media_id for {filename}")
        return media_id

    async def _resolve_image_source(self, source: str) -> tuple[bytes, str]:
        parsed = urlparse(source)
        if source.startswith("data:image/"):
            return self._decode_data_url(source)
        if parsed.scheme in {"http", "https"}:
            return await self._download_remote_image(source)
        if parsed.scheme == "file":
            local_path = Path(parsed.path.lstrip("/"))
            return self._read_local_image(local_path)
        return self._read_local_image(self._resolve_local_path(source))

    async def _download_remote_image(self, url: str) -> tuple[bytes, str]:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                filename = Path(urlparse(str(response.url)).path).name or "image.png"
                return response.content, filename
        except httpx.TimeoutException as exc:
            raise WeChatMediaError(f"Timed out downloading image {url}") from exc
        except httpx.HTTPError as exc:
            raise WeChatMediaError(f"Failed to download image {url}: {exc}") from exc

    def _read_local_image(self, path: Path) -> tuple[bytes, str]:
        if not path.exists() or not path.is_file():
            raise WeChatMediaError(f"Local image not found: {path}")
        suffix = path.suffix.lower().lstrip(".")
        if suffix and suffix not in self.SUPPORTED_IMAGE_TYPES:
            raise WeChatMediaError(f"Unsupported local image type: {path.suffix}")
        return path.read_bytes(), path.name

    def _resolve_local_path(self, source: str) -> Path:
        raw = source.strip()
        candidate = Path(raw)
        if candidate.is_absolute():
            return candidate

        stripped = raw.lstrip("/\\")
        possible_paths = [Path(raw), Path(stripped)]
        for root in self.STATIC_CANDIDATE_ROOTS:
            possible_paths.append(root / raw)
            possible_paths.append(root / stripped)

        for path in possible_paths:
            if path.exists():
                return path.resolve()

        return candidate.resolve()

    def _decode_data_url(self, source: str) -> tuple[bytes, str]:
        header, encoded = source.split(",", 1)
        match = re.match(r"data:image/([a-zA-Z0-9+.-]+);base64", header)
        extension = match.group(1).replace("jpeg", "jpg") if match else "png"
        try:
            image_bytes = base64.b64decode(encoded)
        except ValueError as exc:
            raise WeChatMediaError("Invalid base64 image data URL") from exc
        return image_bytes, f"inline-image.{extension}"

    def _guess_mime_type(self, filename: str) -> str:
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "image/png"

    async def _get_config_for_account(self, account_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        result = await db.execute(select(WeChatConfigModel).where(WeChatConfigModel.account_id == account_id))
        return result.scalar_one_or_none()

    def _is_wechat_host(self, source: str) -> bool:
        lowered = source.lower()
        return "mmbiz.qpic.cn" in lowered or "mmbiz.qlogo.cn" in lowered


wechat_media_service = WeChatMediaService()
