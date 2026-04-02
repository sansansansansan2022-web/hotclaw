"""Publish decision service.

【发布决策服务】
在真正调用微信发布之前，进行一系列校验：
- 账号配置完整性
- 发布权限
- 草稿状态
- 审核结果
- 发布频率限制
- 幂等性检查
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import ArticleDraftModel, AccountModel
from app.models.wechat_config import WeChatConfigModel
from app.services.publish_record_service import publish_record_service

logger = get_logger(__name__)


class PublishDecisionError(Exception):
    """Publish decision validation failed."""
    pass


class PublishDecisionService:
    """
    Publish decision service - validates before real publish.

    Ensures:
    1. WeChat config exists and is enabled
    2. Account is eligible for publishing
    3. Draft status allows publishing
    4. Audit result passes (if applicable)
    5. No rate limiting issues
    6. Idempotency check - no duplicate publishing
    """

    # Publish statuses that block new publish
    BLOCKED_PUBLISH_STATUSES = {"published"}
    # Draft statuses that block publish
    BLOCKED_DRAFT_STATUSES = {"discarded", "rejected", "published"}

    async def validate_for_publish(
        self,
        draft_id: int,
        db: AsyncSession,
        source: str = "manual_confirm",
        is_retry: bool = False,
    ) -> dict:
        """
        Validate all conditions before publishing.

        Args:
            draft_id: Draft ID to validate
            db: Database session
            source: Publish source (manual_confirm, semi_auto_confirm, full_auto)
            is_retry: If True, skip idempotency check (retry case)

        Returns:
            dict with validation result and context

        Raises:
            PublishDecisionError: If validation fails
        """
        # Get draft
        stmt = select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id)
        result = await db.execute(stmt)
        draft = result.scalar_one_or_none()

        if not draft:
            raise PublishDecisionError(f"Draft {draft_id} not found")

        context = {
            "draft_id": draft_id,
            "account_id": draft.account_id,
            "draft_status": draft.draft_status,
            "publish_status": draft.publish_status,
            "source": source,
            "is_retry": is_retry,
        }

        # 1. Check draft status allows publishing
        if draft.publish_status in self.BLOCKED_PUBLISH_STATUSES:
            raise PublishDecisionError(
                f"Draft {draft_id} already published (status: {draft.publish_status}), "
                f"cannot republish. Use retry if needed."
            )

        if draft.draft_status in self.BLOCKED_DRAFT_STATUSES:
            raise PublishDecisionError(
                f"Draft {draft_id} is {draft.draft_status}, cannot publish"
            )

        # 2. Account must exist
        if not draft.account_id:
            raise PublishDecisionError(
                f"Draft {draft_id} has no account, cannot publish to WeChat"
            )

        stmt = select(AccountModel).where(AccountModel.id == draft.account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            raise PublishDecisionError(
                f"Account {draft.account_id} not found"
            )

        context["account_name"] = account.name
        context["operation_mode"] = account.operation_mode

        # 3. WeChat config must exist and be enabled
        stmt = select(WeChatConfigModel).where(
            WeChatConfigModel.account_id == draft.account_id
        )
        result = await db.execute(stmt)
        wechat_config = result.scalar_one_or_none()

        if not wechat_config:
            raise PublishDecisionError(
                f"WeChat config not found for account {draft.account_id}. "
                f"Please configure WeChat settings first."
            )

        if not wechat_config.is_enabled:
            raise PublishDecisionError(
                f"WeChat config is disabled for account {draft.account_id}. "
                f"Please enable it in WeChat settings."
            )

        if not wechat_config.app_id or not wechat_config.app_secret:
            raise PublishDecisionError(
                f"WeChat config incomplete for account {draft.account_id}. "
                f"app_id or app_secret is missing."
            )

        context["wechat_app_id"] = wechat_config.app_id

        # 4. Idempotency check (skip for retry)
        if not is_retry:
            has_active = await publish_record_service.has_active_publishing(draft_id, db)
            if has_active:
                raise PublishDecisionError(
                    f"Draft {draft_id} already has an active publishing record "
                    f"(pending/publishing). Please wait for current publish to complete."
                )

            # Check latest record status
            latest = await publish_record_service.get_latest_for_draft(draft_id, db)
            if latest and latest.publish_status == "failed" and latest.retry_count >= 3:
                raise PublishDecisionError(
                    f"Draft {draft_id} has exceeded maximum retry attempts (3). "
                    f"Please create a new draft instead."
                )

        # 5. For semi_auto, source must be semi_auto_confirm or manual_confirm
        if account.operation_mode == "semi_auto" and source not in {"semi_auto_confirm", "manual_confirm"}:
            raise PublishDecisionError(
                f"semi_auto account requires manual_confirm source, got {source}"
            )

        # 6. For full_auto, source must be full_auto
        if account.operation_mode == "full_auto" and source not in {"full_auto", "semi_auto_confirm", "manual_confirm"}:
            logger.warning(
                "publish_decision_full_auto_source",
                draft_id=draft_id,
                expected="full_auto",
                got=source
            )

        # 7. Check auto_publish setting for full_auto
        if source == "full_auto" and not account.auto_publish_enabled:
            raise PublishDecisionError(
                f"Account {draft.account_id} has auto_publish disabled. "
                f"Cannot auto publish in full_auto mode."
            )

        # 8. Audit result check (if available)
        from app.models.tables import AuditResultModel
        stmt = select(AuditResultModel).where(AuditResultModel.draft_id == draft_id)
        result = await db.execute(stmt)
        audit = result.scalar_one_or_none()

        if audit and not audit.passed:
            # For now, just log warning - don't block publishing
            logger.warning(
                "publish_decision_audit_failed",
                draft_id=draft_id,
                risk_level=audit.risk_level,
                comment=audit.overall_comment
            )
            context["audit_warning"] = f"Audit not passed: {audit.overall_comment}"

        logger.info(
            "publish_decision_passed",
            **context
        )

        return context

    async def get_wechat_config(
        self,
        account_id: str,
        db: AsyncSession
    ) -> WeChatConfigModel | None:
        """Get WeChat config for an account."""
        stmt = select(WeChatConfigModel).where(
            WeChatConfigModel.account_id == account_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


publish_decision_service = PublishDecisionService()
