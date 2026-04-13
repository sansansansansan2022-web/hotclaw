"""High-level WeChat publish orchestration service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DraftPublishError
from app.core.logger import get_logger
from app.db.session import get_db_context
from app.models.tables import AccountModel, ArticleDraftModel
from app.models.wechat_config import WeChatConfigModel
from app.schemas.wechat import PublishResult
from app.services.e2e_test_mode_service import e2e_test_mode_service
from app.services.publish_decision_service import PublishDecisionError, publish_decision_service
from app.services.publish_record_service import PublishRecordError, publish_record_service
from app.services.wechat_draft_service import WeChatDraftError, wechat_draft_service
from app.services.wechat_media_service import WeChatMediaError, wechat_media_service
from app.services.wechat_token_service import WeChatTokenError, wechat_token_service

logger = get_logger(__name__)


class WeChatPublishError(Exception):
    """WeChat publish related errors."""


class WeChatPublishService:
    """Orchestrate publish decision, media upload, WeChat draft creation, and submit."""

    WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
    WECHAT_STATUS_MAP = {
        0: publish_record_service.STATUS_SUBMITTED,
        1: publish_record_service.STATUS_POLLING,
        2: publish_record_service.STATUS_PUBLISHED,
        3: publish_record_service.STATUS_FAILED,
        4: publish_record_service.STATUS_FAILED,
    }

    async def publish_draft_to_wechat(
        self,
        draft_id: int,
        *,
        operator: str = "system",
        source_mode: str = "manual",
        trigger_type: str = publish_record_service.TRIGGER_MANUAL_CONFIRM,
        existing_record_id: int | None = None,
        db: AsyncSession | None = None,
    ) -> PublishResult:
        """Publish a HotClaw draft through the WeChat draft + freepublish flow."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.publish_draft_to_wechat(
                    draft_id,
                    operator=operator,
                    source_mode=source_mode,
                    trigger_type=trigger_type,
                    existing_record_id=existing_record_id,
                    db=managed_db,
                )

        draft = await self._get_draft(draft_id, db)
        decision = await publish_decision_service.decide_publish(
            draft_id,
            db,
            source=trigger_type,
            is_retry=existing_record_id is not None,
        )

        if decision.is_block():
            raise PublishDecisionError(
                decision=decision.decision.value,
                reason_code=decision.reason_code.value,
                message=decision.reason_message,
            )

        if decision.is_skip() or decision.is_save_as_draft():
            draft.publish_error_message = f"[{decision.reason_code.value}] {decision.reason_message}"
            if decision.is_skip():
                draft.publish_status = "failed"
            db.add(draft)
            await db.flush()
            return PublishResult(
                success=False,
                draft_id=draft_id,
                publish_status=draft.publish_status,
                error_code=decision.reason_code.value,
                error_message=decision.reason_message,
                decision=decision.to_dict(),
            )

        config = await publish_decision_service.get_wechat_config(draft.account_id, db)
        if not config:
            raise DraftPublishError(draft_id, f"WeChat config not found for account {draft.account_id}")

        record = await self._get_or_create_publish_record(
            draft,
            db,
            source_mode=source_mode,
            trigger_type=trigger_type,
            existing_record_id=existing_record_id,
        )

        try:
            publish_mode = await e2e_test_mode_service.get_publish_mode(db)
            if publish_mode == e2e_test_mode_service.MODE_FAKE_FAILURE:
                error_message = await e2e_test_mode_service.get_publish_failure_message(db)
                await self._mark_publish_failure(
                    record.id,
                    draft,
                    db,
                    error_code="E2E_FAKE_PUBLISH",
                    error_message=error_message,
                )
                raise DraftPublishError(draft_id, error_message)

            if publish_mode == e2e_test_mode_service.MODE_FAKE_SUCCESS:
                fake_media_id = f"e2e-media-{record.id}"
                fake_publish_id = f"e2e-publish-{record.id}"
                fake_article_id = f"e2e-article-{record.id}"
                fake_url = f"https://example.test/hotclaw/publish/{record.id}"

                draft.draft_status = "approved" if draft.draft_status in {"draft", "pending_review"} else draft.draft_status
                draft.publish_status = "pending"
                draft.confirmed_at = draft.confirmed_at or datetime.now(timezone.utc)
                draft.confirmed_by = operator
                draft.publish_error_message = None
                db.add(draft)
                await db.flush()

                await publish_record_service.update_success(
                    record.id,
                    db,
                    wechat_draft_id=fake_media_id,
                    media_id=fake_media_id,
                    publish_id=fake_publish_id,
                    article_id=fake_article_id,
                    url=fake_url,
                    response_snapshot="simulated=true;source=e2e_fake;provider=fake;event=publish_success",
                )
                await publish_record_service.sync_draft_status(draft.id, db)
                refreshed_record = await publish_record_service.get_record(record.id, db)
                await self._sync_account_publish_status(
                    draft.account_id,
                    db,
                    status=publish_record_service.STATUS_PUBLISHED,
                    error_message=None,
                )
                return PublishResult(
                    success=True,
                    draft_id=draft_id,
                    publish_record_id=record.id,
                    wechat_draft_media_id=fake_media_id,
                    wechat_publish_id=fake_publish_id,
                    wechat_article_url=fake_url,
                    publish_status=publish_record_service.STATUS_PUBLISHED,
                    decision=decision.to_dict(),
                    published_at=refreshed_record.published_at if refreshed_record else None,
                    simulated=True,
                    simulation_source="e2e_fake",
                    provider="fake",
                )

            await publish_record_service.update_status(
                record.id,
                db,
                status=publish_record_service.STATUS_UPLOADING_MEDIA,
            )

            content_html = draft.content_html or wechat_draft_service._markdown_to_html(draft.content_markdown)
            rewritten_html, derived_thumb_media_id = await wechat_media_service.rewrite_article_html_images(
                content_html,
                draft.account_id,
                db,
            )

            thumb_media_id = config.default_thumb_media_id or derived_thumb_media_id

            await publish_record_service.update_status(
                record.id,
                db,
                status=publish_record_service.STATUS_CREATING_DRAFT,
            )

            draft_result = await wechat_draft_service.create_wechat_draft(
                draft.account_id,
                draft.id,
                db,
                content_html=rewritten_html,
                thumb_media_id=thumb_media_id,
                author_name=config.default_author,
                digest=draft.summary,
            )
            wechat_draft_media_id = draft_result["media_id"]

            await publish_record_service.update_status(
                record.id,
                db,
                status=publish_record_service.STATUS_SUBMITTED,
                wechat_draft_id=wechat_draft_media_id,
                media_id=wechat_draft_media_id,
                response_snapshot=f"draft_created:{wechat_draft_media_id}",
            )

            submit_result = await self.free_publish(config.id, wechat_draft_media_id, db)
            await publish_record_service.update_status(
                record.id,
                db,
                status=publish_record_service.STATUS_SUBMITTED,
                publish_id=submit_result.get("publish_id"),
                article_id=submit_result.get("msg_data_id"),
                response_snapshot=f"submitted:{submit_result.get('publish_id')}",
            )

            draft.draft_status = "approved" if draft.draft_status in {"draft", "pending_review"} else draft.draft_status
            draft.publish_status = "pending"
            draft.confirmed_at = draft.confirmed_at or datetime.now(timezone.utc)
            draft.confirmed_by = operator
            draft.publish_error_message = None
            db.add(draft)
            await db.flush()

            await self._sync_account_publish_status(
                draft.account_id,
                db,
                status=publish_record_service.STATUS_SUBMITTED,
                error_message=None,
            )

            await self.sync_publish_status(record.id, db, raise_on_missing_publish_id=False)
            refreshed_record = await publish_record_service.get_record(record.id, db)

            final_status = refreshed_record.publish_status if refreshed_record else publish_record_service.STATUS_SUBMITTED
            return PublishResult(
                success=final_status != publish_record_service.STATUS_FAILED,
                draft_id=draft_id,
                publish_record_id=record.id,
                wechat_draft_media_id=wechat_draft_media_id,
                wechat_publish_id=submit_result.get("publish_id"),
                wechat_article_url=refreshed_record.url if refreshed_record else None,
                publish_status=final_status,
                decision=decision.to_dict(),
                published_at=refreshed_record.published_at if refreshed_record else None,
                simulated=False,
                simulation_source=None,
                provider="wechat",
            )
        except DraftPublishError:
            raise
        except PublishDecisionError:
            raise
        except (WeChatTokenError, WeChatMediaError, WeChatDraftError, WeChatPublishError) as exc:
            await self._mark_publish_failure(record.id, draft, db, error_code=type(exc).__name__, error_message=str(exc))
            raise DraftPublishError(draft_id, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            await self._mark_publish_failure(record.id, draft, db, error_code="INTERNAL_ERROR", error_message=str(exc))
            raise DraftPublishError(draft_id, f"Unexpected publish error: {exc}") from exc

    async def sync_publish_status(
        self,
        publish_record_id: int,
        db: AsyncSession | None = None,
        *,
        raise_on_missing_publish_id: bool = True,
    ) -> dict[str, Any]:
        """Query WeChat and sync local publish record and draft state."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.sync_publish_status(
                    publish_record_id,
                    managed_db,
                    raise_on_missing_publish_id=raise_on_missing_publish_id,
                )

        record = await publish_record_service.get_record(publish_record_id, db)
        if not record:
            raise PublishRecordError(f"Publish record {publish_record_id} not found")

        previous_status = record.publish_status
        simulation_meta = publish_record_service.get_simulation_metadata(record)
        if simulation_meta.get("simulated"):
            synced = await publish_record_service.sync_draft_status(record.draft_id, db)
            return {
                "record_id": record.id,
                "previous_status": previous_status,
                "new_status": previous_status,
                "synced_draft": bool(synced.get("synced")),
                "message": "Simulated publish record is already in sync",
            }

        if not record.publish_id:
            if raise_on_missing_publish_id:
                raise WeChatPublishError(f"Publish record {publish_record_id} has no publish_id")
            return {
                "record_id": publish_record_id,
                "previous_status": previous_status,
                "new_status": previous_status,
                "synced_draft": False,
                "message": "publish_id is not available yet",
            }

        config = await self._get_config_by_account_id(record.account_id, db)
        if not config:
            raise WeChatPublishError(f"WeChat config not found for account {record.account_id}")

        status_result = await self.get_publish_status(config.id, record.publish_id, db)
        new_status = status_result["status"]

        record_kwargs: dict[str, Any] = {
            "article_id": status_result.get("article_id"),
            "url": status_result.get("article_url"),
            "response_snapshot": f"status:{status_result.get('publish_status_code')}",
        }
        await publish_record_service.update_status(record.id, db, status=new_status, **record_kwargs)

        synced = await publish_record_service.sync_draft_status(record.draft_id, db)
        return {
            "record_id": record.id,
            "previous_status": previous_status,
            "new_status": new_status,
            "synced_draft": bool(synced.get("synced")),
            "message": status_result.get("message", "status synced"),
        }

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
        only_fans_can_comment: bool = False,
    ) -> dict[str, Any]:
        """Legacy low-level publish helper kept for backward compatibility."""

        media_id = await wechat_draft_service.create_draft(
            app_id,
            app_secret,
            title,
            author,
            digest,
            content_html,
            None,
            thumb_media_id,
            need_open_comment,
            only_fans_can_comment,
        )
        submit_result = await self._free_publish_by_credentials(app_id, app_secret, media_id)
        return {
            "success": True,
            "media_id": media_id,
            "publish_id": submit_result.get("publish_id"),
            "msg_id": submit_result.get("msg_data_id"),
            "url": submit_result.get("article_url"),
            "article_id": submit_result.get("msg_data_id"),
        }

    async def free_publish(
        self,
        config_id: int | str,
        media_id: str,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Submit a WeChat draft for publish."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.free_publish(config_id, media_id, managed_db)

        config = await self._get_config(config_id, db)
        token = await wechat_token_service.get_valid_access_token(config.id, db)
        return await self._free_publish_by_token(token, media_id)

    async def get_publish_status(
        self,
        config_id: int | str,
        publish_id: str,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Get publish status from WeChat and map it to local statuses."""

        if db is None:
            async with get_db_context() as managed_db:
                return await self.get_publish_status(config_id, publish_id, managed_db)

        config = await self._get_config(config_id, db)
        token = await wechat_token_service.get_valid_access_token(config.id, db)
        data = await self._call_wechat(token, "/freepublish/getpubstatus", {"publish_id": publish_id})
        raw_status = data.get("publish_status")
        mapped_status = self.WECHAT_STATUS_MAP.get(raw_status, publish_record_service.STATUS_UNKNOWN)
        return {
            "status": mapped_status,
            "message": f"WeChat publish status {raw_status}",
            "article_id": data.get("article_id") or data.get("msg_data_id"),
            "msg_data_id": data.get("msg_data_id"),
            "article_url": data.get("article_url") or data.get("url"),
            "publish_status_code": raw_status,
        }

    async def _free_publish_by_credentials(self, app_id: str, app_secret: str, media_id: str) -> dict[str, Any]:
        token = await wechat_token_service.get_access_token(app_id, app_secret)
        return await self._free_publish_by_token(token, media_id)

    async def _free_publish_by_token(self, access_token: str, media_id: str) -> dict[str, Any]:
        return await self._call_wechat(access_token, "/freepublish/submit", {"media_id": media_id})

    async def _call_wechat(self, access_token: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.WECHAT_API_BASE}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params={"access_token": access_token}, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise WeChatPublishError(f"WeChat publish request timeout for {endpoint}") from exc
        except httpx.HTTPError as exc:
            raise WeChatPublishError(f"WeChat publish request failed for {endpoint}: {exc}") from exc
        except ValueError as exc:
            raise WeChatPublishError(f"Invalid WeChat publish response for {endpoint}") from exc

        if data.get("errcode") not in (None, 0):
            raise WeChatPublishError(f"WeChat publish API error {data.get('errcode')}: {data.get('errmsg')}")
        return data

    async def _get_or_create_publish_record(
        self,
        draft: ArticleDraftModel,
        db: AsyncSession,
        *,
        source_mode: str,
        trigger_type: str,
        existing_record_id: int | None,
    ):
        if existing_record_id:
            record = await publish_record_service.get_record(existing_record_id, db)
            if not record:
                raise PublishRecordError(f"Publish record {existing_record_id} not found")
            await publish_record_service.update_status(
                record.id,
                db,
                status=publish_record_service.STATUS_PENDING,
                finished_at=None,
                published_at=None,
                error_code=None,
                error_message=None,
                response_snapshot=None,
            )
            return record

        request_snapshot = f"title={draft.title[:80]}"
        return await publish_record_service.create_record(
            draft_id=draft.id,
            account_id=draft.account_id,
            task_id=draft.task_id,
            db=db,
            source_mode=source_mode,
            trigger_type=trigger_type,
            request_snapshot=request_snapshot,
        )

    async def _mark_publish_failure(
        self,
        record_id: int,
        draft: ArticleDraftModel,
        db: AsyncSession,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        await publish_record_service.update_failed(
            record_id,
            db,
            error_code=error_code,
            error_message=error_message[:500],
            response_snapshot=self._build_failure_snapshot(error_code),
        )
        draft.publish_status = "failed"
        if draft.draft_status == "published":
            draft.draft_status = "approved"
        draft.publish_error_message = f"[{error_code}] {error_message[:200]}"
        db.add(draft)
        await db.flush()
        await self._sync_account_publish_status(
            draft.account_id,
            db,
            status=publish_record_service.STATUS_FAILED,
            error_message=error_message,
        )
        logger.warning(
            "wechat_publish_pipeline_failed",
            draft_id=draft.id,
            publish_record_id=record_id,
            error_code=error_code,
            error_message=error_message,
        )

    def _build_failure_snapshot(self, error_code: str) -> str:
        if error_code == "E2E_FAKE_PUBLISH":
            return "simulated=true;source=e2e_fake;provider=fake;event=publish_failed"
        return f"failed:{error_code}"

    async def _sync_account_publish_status(
        self,
        account_id: str | None,
        db: AsyncSession,
        *,
        status: str,
        error_message: str | None,
    ) -> None:
        if not account_id:
            return

        update_data: dict[str, Any] = {"last_publish_status": status}
        if error_message is not None:
            update_data["last_publish_error_message"] = error_message[:500] if error_message else None
        if status == publish_record_service.STATUS_PUBLISHED:
            update_data["last_published_at"] = datetime.now(timezone.utc)

        await db.execute(update(AccountModel).where(AccountModel.id == account_id).values(**update_data))
        await db.flush()

    async def _get_draft(self, draft_id: int, db: AsyncSession) -> ArticleDraftModel:
        result = await db.execute(select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id))
        draft = result.scalar_one_or_none()
        if not draft:
            raise DraftPublishError(draft_id, f"Draft {draft_id} not found")
        return draft

    async def _get_config(self, config_id: int | str, db: AsyncSession) -> WeChatConfigModel:
        if isinstance(config_id, str) and not config_id.isdigit():
            config = await self._get_config_by_account_id(config_id, db)
        else:
            config = await db.get(WeChatConfigModel, int(config_id))
        if not config:
            raise WeChatPublishError(f"WeChat config {config_id} not found")
        return config

    async def _get_config_by_account_id(self, account_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        result = await db.execute(select(WeChatConfigModel).where(WeChatConfigModel.account_id == account_id))
        return result.scalar_one_or_none()


wechat_publish_service = WeChatPublishService()
