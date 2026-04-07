"""Service layer for account-bound WeChat configuration."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import AccountModel
from app.models.wechat_config import WeChatConfigModel
from app.schemas.wechat import (
    WeChatConfigCreate,
    WeChatConfigRead,
    WeChatConfigUpdate,
    WeChatConnectionTestResponse,
)

logger = get_logger(__name__)


class WeChatConfigServiceError(Exception):
    """Service-level WeChat configuration error."""


class WeChatConfigService:
    """CRUD and projection helpers for WeChat account configuration."""

    @staticmethod
    def mask_app_id(app_id: str) -> str:
        if not app_id:
            return "****"
        if len(app_id) <= 8:
            return f"{app_id[:2]}****"
        return f"{app_id[:4]}****{app_id[-4:]}"

    @staticmethod
    def mask_secret(app_secret: str | None) -> str | None:
        if not app_secret:
            return None
        if len(app_secret) <= 6:
            return "******"
        return f"{app_secret[:2]}******{app_secret[-2:]}"

    def to_read_model(self, config: WeChatConfigModel) -> WeChatConfigRead:
        verified_at = config.last_sync_at if config.test_status == "success" else None
        return WeChatConfigRead(
            account_id=config.account_id,
            app_id_masked=self.mask_app_id(config.app_id),
            has_app_secret=bool(config.app_secret),
            app_secret_masked=self.mask_secret(config.app_secret),
            default_author=config.default_author,
            default_thumb_media_id=config.default_thumb_media_id,
            need_open_comment=config.need_open_comment,
            only_fans_can_comment=config.only_fans_can_comment,
            is_enabled=config.is_enabled,
            access_token_cached=bool(config.access_token),
            token_expires_at=config.access_token_expires_at,
            verified_at=verified_at,
            last_test_status=config.test_status,
            last_test_error=config.test_message,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    async def get_by_account_id(self, account_id: str, db: AsyncSession) -> WeChatConfigModel | None:
        result = await db.execute(select(WeChatConfigModel).where(WeChatConfigModel.account_id == account_id))
        return result.scalar_one_or_none()

    async def get_or_raise(self, account_id: str, db: AsyncSession) -> WeChatConfigModel:
        config = await self.get_by_account_id(account_id, db)
        if not config:
            raise WeChatConfigServiceError(f"WeChat config not found for account {account_id}")
        return config

    async def create(self, account_id: str, payload: WeChatConfigCreate, db: AsyncSession) -> WeChatConfigModel:
        account = await db.get(AccountModel, account_id)
        if not account:
            raise WeChatConfigServiceError(f"Account {account_id} not found")

        existing = await self.get_by_account_id(account_id, db)
        if existing:
            raise WeChatConfigServiceError(f"WeChat config already exists for account {account_id}")

        config = WeChatConfigModel(
            account_id=account_id,
            app_id=payload.app_id,
            app_secret=payload.app_secret,
            default_author=payload.default_author,
            default_thumb_media_id=payload.default_thumb_media_id,
            need_open_comment=payload.need_open_comment,
            only_fans_can_comment=payload.only_fans_can_comment,
            is_enabled=payload.is_enabled,
            test_status="untested",
            test_message=None,
        )
        db.add(config)
        await db.flush()
        await db.refresh(config)
        logger.info("wechat_config_created", account_id=account_id)
        return config

    async def update(self, account_id: str, payload: WeChatConfigUpdate, db: AsyncSession) -> WeChatConfigModel:
        config = await self.get_or_raise(account_id, db)
        updates = payload.model_dump(exclude_unset=True)

        credentials_changed = False
        for key, value in updates.items():
            if value is None:
                continue
            setattr(config, key, value)
            if key in {"app_id", "app_secret"}:
                credentials_changed = True

        if credentials_changed:
            config.access_token = None
            config.access_token_expires_at = None
            config.test_status = "untested"
            config.test_message = None

        db.add(config)
        await db.flush()
        await db.refresh(config)
        logger.info("wechat_config_updated", account_id=account_id, updated_fields=list(updates.keys()))
        return config

    async def test_connection(self, account_id: str, db: AsyncSession) -> WeChatConnectionTestResponse:
        from app.services.wechat_token_service import wechat_token_service

        config = await self.get_or_raise(account_id, db)
        result = await wechat_token_service.test_connection(config.id, db)

        config.test_status = "success" if result["success"] else "failed"
        config.test_message = None if result["success"] else result["message"]
        config.last_sync_at = result["tested_at"]
        db.add(config)
        await db.flush()

        return WeChatConnectionTestResponse(
            success=result["success"],
            message=result["message"],
            tested_at=result["tested_at"],
            token_expires_at=result.get("token_expires_at"),
        )

    async def test_credentials(self, app_id: str, app_secret: str) -> WeChatConnectionTestResponse:
        from app.services.wechat_token_service import wechat_token_service

        result = await wechat_token_service.test_credentials(app_id, app_secret)
        return WeChatConnectionTestResponse(
            success=result["success"],
            message=result["message"],
            tested_at=result["tested_at"],
            token_expires_at=result.get("token_expires_at"),
        )


wechat_config_service = WeChatConfigService()
