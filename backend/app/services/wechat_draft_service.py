"""WeChat draft service."""

from __future__ import annotations

import re
from html import unescape
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.db.session import get_db_context
from app.models.tables import ArticleDraftModel
from app.services.wechat_config_service import wechat_config_service
from app.services.wechat_token_service import wechat_token_service

logger = get_logger(__name__)


class WeChatDraftError(Exception):
    """WeChat draft related errors."""


class WeChatDraftService:
    """Convert HotClaw drafts into WeChat draft payloads and create remote drafts."""

    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
    DIGEST_LIMIT = 120

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
        only_fans_can_comment: bool = False,
    ) -> str:
        """Legacy compatibility wrapper for low-level WeChat draft creation."""

        token = await wechat_token_service.get_access_token(app_id, app_secret)
        payload = {
            "articles": [
                {
                    "title": title,
                    "author": author or "",
                    "digest": self._clip_digest(digest or title),
                    "content": self._sanitize_html(content),
                    "content_source_url": content_source_url or "",
                    "thumb_media_id": thumb_media_id or "",
                    "need_open_comment": 1 if need_open_comment else 0,
                    "only_fans_can_comment": 1 if only_fans_can_comment else 0,
                }
            ]
        }
        result = await self._call_wechat(token, "/draft/add", payload)
        media_id = result.get("media_id")
        if not media_id:
            raise WeChatDraftError("WeChat draft creation returned no media_id")
        return media_id

    def build_wechat_article_payload(
        self,
        draft: ArticleDraftModel,
        thumb_media_id: str | None,
        author_name: str | None = None,
        digest: str | None = None,
        *,
        content_html: str | None = None,
        need_open_comment: bool = True,
        only_fans_can_comment: bool = False,
    ) -> dict[str, Any]:
        """Build the single-article payload used by WeChat draft/add."""

        normalized_html = self._sanitize_html(content_html or draft.content_html or self._markdown_to_html(draft.content_markdown))
        article_digest = self._build_digest(draft, digest=digest, content_html=normalized_html)
        return {
            "title": (draft.title or "Untitled").strip()[:64],
            "author": (author_name or "").strip(),
            "digest": article_digest,
            "content": normalized_html,
            "content_source_url": "",
            "thumb_media_id": thumb_media_id or "",
            "need_open_comment": 1 if need_open_comment else 0,
            "only_fans_can_comment": 1 if only_fans_can_comment else 0,
        }

    async def create_wechat_draft(
        self,
        account_id: str,
        draft_id: int,
        db: AsyncSession | None = None,
        *,
        content_html: str | None = None,
        thumb_media_id: str | None = None,
        author_name: str | None = None,
        digest: str | None = None,
    ) -> dict[str, Any]:
        """Create a remote WeChat draft for a HotClaw draft."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.create_wechat_draft(
                    account_id,
                    draft_id,
                    managed_db,
                    content_html=content_html,
                    thumb_media_id=thumb_media_id,
                    author_name=author_name,
                    digest=digest,
                )

        draft = await managed_db_get_draft(draft_id, db)
        config = await wechat_config_service.get_or_raise(account_id, db)
        token = await wechat_token_service.get_valid_access_token(config.id, db)

        payload = {
            "articles": [
                self.build_wechat_article_payload(
                    draft,
                    thumb_media_id or config.default_thumb_media_id,
                    author_name=author_name or config.default_author,
                    digest=digest,
                    content_html=content_html,
                    need_open_comment=config.need_open_comment,
                    only_fans_can_comment=config.only_fans_can_comment,
                )
            ]
        }

        result = await self._call_wechat(token, "/draft/add", payload)
        media_id = result.get("media_id")
        if not media_id:
            raise WeChatDraftError("WeChat draft creation returned no media_id")

        logger.info("wechat_draft_created", account_id=account_id, draft_id=draft_id, media_id=media_id)
        return {"media_id": media_id, "payload": payload}

    async def _call_wechat(self, access_token: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.WECHAT_API_BASE}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params={"access_token": access_token}, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise WeChatDraftError(f"WeChat draft request timeout for {endpoint}") from exc
        except httpx.HTTPError as exc:
            raise WeChatDraftError(f"WeChat draft request failed for {endpoint}: {exc}") from exc
        except ValueError as exc:
            raise WeChatDraftError(f"Invalid WeChat draft response for {endpoint}") from exc

        if data.get("errcode") not in (None, 0):
            raise WeChatDraftError(f"WeChat draft API error {data.get('errcode')}: {data.get('errmsg')}")
        return data

    def _build_digest(
        self,
        draft: ArticleDraftModel,
        *,
        digest: str | None = None,
        content_html: str | None = None,
    ) -> str:
        if digest:
            return self._clip_digest(digest)
        if draft.summary:
            return self._clip_digest(draft.summary)

        text = self._strip_html_tags(content_html or draft.content_html or self._markdown_to_html(draft.content_markdown))
        return self._clip_digest(text or draft.title or "HotClaw article")

    def _clip_digest(self, digest: str) -> str:
        normalized = re.sub(r"\s+", " ", unescape(digest or "")).strip()
        return normalized[: self.DIGEST_LIMIT]

    def _sanitize_html(self, html: str) -> str:
        """Perform light cleanup for WeChat draft compatibility.

        We keep this deliberately small:
        - remove script/style/iframe blocks because WeChat strips them anyway
        - remove inline event handlers to avoid invalid attributes
        - normalize empty paragraphs so the editor does not collapse spacing too aggressively
        """

        sanitized = html or ""
        sanitized = re.sub(r"<(script|style|iframe)[^>]*>.*?</\1>", "", sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r"\son[a-z]+=(\"[^\"]*\"|'[^']*')", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"<p>\s*</p>", "<p><br/></p>", sanitized)
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
        return sanitized.strip()

    def _strip_html_tags(self, html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html or "")
        return re.sub(r"\s+", " ", unescape(text)).strip()

    def _markdown_to_html(self, markdown: str) -> str:
        if not markdown:
            return ""
        html = markdown
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        paragraphs = [segment.strip() for segment in re.split(r"\n{2,}", html) if segment.strip()]
        return "".join(f"<p>{segment.replace(chr(10), '<br/>')}</p>" for segment in paragraphs)


async def managed_db_get_draft(draft_id: int, db: AsyncSession) -> ArticleDraftModel:
    from sqlalchemy import select

    result = await db.execute(select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise WeChatDraftError(f"Draft {draft_id} not found")
    return draft


wechat_draft_service = WeChatDraftService()
