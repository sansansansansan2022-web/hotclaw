"""
Draft Service - 草稿服务模块

本模块负责内容草稿生命周期管理的核心业务逻辑，包括：
- 从任务结果自动创建草稿
- 草稿详情查询与列表分页
- 草稿发布确认流程（confirm_publish）
- 草稿发布到微信公众号
- 草稿废弃/拒绝/重跑操作
- 发布状态与账号发布状态同步

草稿状态机：
- draft（草稿） -> pending_review（待审核） -> approved（已批准） -> published（已发布）
- draft（草稿） -> discarded（已废弃）
- pending_review（待审核） -> rejected（已拒绝） / discarded（已废弃）
- approved（已批准） -> published（已发布）
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DraftNotFoundError,
    DraftInvalidStatusError,
    DraftAlreadyPublishedError,
    DraftPublishError,
    DraftCreateError,
)
from app.core.logger import get_logger
from app.core.tracer import generate_task_id
from app.models.tables import ArticleDraftModel, AuditResultModel, TaskModel, AccountModel
from app.models.wechat_config import WeChatConfigModel, WeChatPublishRecordModel
from app.services.article_assembler_service import article_assembler_service

logger = get_logger(__name__)

# Valid state transitions
VALID_TRANSITIONS = {
    "draft": {"pending_review", "discarded"},
    "pending_review": {"approved", "rejected", "discarded"},
    "approved": {"published"},
    "rejected": set(),  # Terminal state
    "discarded": set(),  # Terminal state
    "published": set(),  # Terminal state
}


class DraftService:

    async def create_draft_from_task(
        self,
        task_id: str,
        result_data: dict,
        account_id: str | None,
        operation_mode: str | None,
        db: AsyncSession
    ) -> ArticleDraftModel:
        """
        Create a draft from task result data.

        For semi_auto accounts, the draft will be in 'pending_review' status.
        For manual accounts, the draft will be in 'draft' status.

        Args:
            task_id: The task ID
            result_data: The workspace result data from orchestrator
            account_id: The account ID (if any)
            operation_mode: 'manual', 'semi_auto', or 'full_auto'
            db: Database session

        Returns:
            Created ArticleDraftModel
        """
        normalized_result = article_assembler_service.normalize_result_data(result_data)
        content = article_assembler_service.extract_article_payload(normalized_result)

        selected_title = content.get("selected_title", "Untitled")
        title_candidates = content.get("title_candidates", [])
        selected_topic = content.get("selected_topic", "")
        summary = content.get("summary", "")
        main_content = content.get("content_markdown", "")

        # Determine draft status based on operation mode.
        # full_auto drafts can auto-publish later, but they are not yet marked as published.
        if operation_mode == "full_auto":
            draft_status = "approved"
            publish_review_required = False
            source_type = "full_auto_task"
        elif operation_mode == "semi_auto":
            draft_status = "pending_review"
            publish_review_required = True
            source_type = "semi_auto_task"
        else:
            # manual or other modes
            draft_status = "draft"
            publish_review_required = False
            source_type = "manual_task"

        # Create draft
        now = datetime.now(timezone.utc)
        draft = ArticleDraftModel(
            task_id=task_id,
            account_id=account_id,
            title=selected_title[:200] if selected_title else "Untitled",
            title_candidates=title_candidates[:5] if title_candidates else None,  # Keep max 5 candidates
            selected_topic=selected_topic[:500] if selected_topic else None,
            summary=summary[:500] if summary else None,
            content_markdown=main_content,
            content_html=article_assembler_service.ensure_content_html(
                content.get("content_html"),
                main_content,
            ),
            word_count=self._count_words(main_content),
            tags=content.get("tags"),
            structure=content.get("structure"),
            draft_status=draft_status,
            publish_status="not_published",
            publish_review_required=publish_review_required,
            source_type=source_type,
            # full_auto 由后续发布流程填充 published_at
            confirmed_at=now if operation_mode == "full_auto" else None,
            confirmed_by="system" if operation_mode == "full_auto" else None,
            published_at=None,
        )

        db.add(draft)
        await db.flush()
        logger.info(
            "draft_created",
            draft_id=draft.id,
            task_id=task_id,
            account_id=account_id,
            draft_status=draft_status,
            source_type=source_type
        )

        return draft

    def _count_words(self, text: str) -> int:
        """Count Chinese + English words in text."""
        if not text:
            return 0
        import re
        # Count Chinese characters + English words
        chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
        english = len(re.findall(r'[a-zA-Z]+', text))
        return chinese + english

    async def get_draft(self, draft_id: int, db: AsyncSession) -> ArticleDraftModel:
        """Get draft by ID."""
        stmt = select(ArticleDraftModel).where(ArticleDraftModel.id == draft_id)
        result = await db.execute(stmt)
        draft = result.scalar_one_or_none()
        if draft is None:
            raise DraftNotFoundError(draft_id)
        return draft

    async def get_draft_detail(
        self, draft_id: int, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Get full draft detail with audit result.
        Returns serializable dict for response.
        """
        draft = await self.get_draft(draft_id, db)

        # Fetch account name if available
        account_name = None
        if draft.account_id:
            stmt = select(AccountModel.name).where(AccountModel.id == draft.account_id)
            result = await db.execute(stmt)
            account_name = result.scalar_one_or_none()

        # Fetch audit result
        audit_result = None
        stmt = select(AuditResultModel).where(AuditResultModel.draft_id == draft_id)
        result = await db.execute(stmt)
        audit = result.scalar_one_or_none()
        if audit:
            audit_result = {
                "passed": audit.passed,
                "risk_level": audit.risk_level,
                "overall_comment": audit.overall_comment,
                "issues": audit.issues,
            }

        task_result = await db.execute(
            select(TaskModel.result_data).where(TaskModel.id == draft.task_id)
        )
        task_result_data = task_result.scalar_one_or_none()
        if not isinstance(task_result_data, dict):
            task_result_data = {}
        task_result_data = article_assembler_service.normalize_result_data(task_result_data)
        content_html = article_assembler_service.ensure_content_html(
            draft.content_html,
            draft.content_markdown,
        )

        return {
            "id": draft.id,
            "task_id": draft.task_id,
            "account_id": draft.account_id,
            "account_name": account_name,
            "title": draft.title,
            "title_candidates": draft.title_candidates,
            "selected_topic": draft.selected_topic,
            "summary": draft.summary,
            "content_markdown": draft.content_markdown,
            "content_html": content_html,
            "word_count": draft.word_count,
            "tags": draft.tags,
            "draft_status": draft.draft_status,
            "publish_status": draft.publish_status,
            "publish_review_required": draft.publish_review_required,
            "source_type": draft.source_type,
            "confirmed_at": draft.confirmed_at.isoformat() if draft.confirmed_at else None,
            "confirmed_by": draft.confirmed_by,
            "published_at": draft.published_at.isoformat() if draft.published_at else None,
            "publish_error_message": draft.publish_error_message,
            "audit_result": audit_result,
            "style_profile": task_result_data.get("style_profile"),
            "retrieved_memories": task_result_data.get("retrieved_memories"),
            "outline_plan": task_result_data.get("outline_plan"),
            "section_drafts": task_result_data.get("section_drafts"),
            "style_review": task_result_data.get("style_review"),
            "structure_review": task_result_data.get("structure_review"),
            "review_results": task_result_data.get("review_results"),
            "rewrite_result": task_result_data.get("rewrite_result"),
            "draft_quality_gate": task_result_data.get("draft_quality_gate"),
            "post_process_result": task_result_data.get("post_process_result"),
            "evaluation": task_result_data.get("evaluation"),
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }

    async def list_drafts(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        account_id: str | None = None,
        draft_status: str | None = None,
        publish_status: str | None = None,
    ) -> tuple[list[ArticleDraftModel], int]:
        """List drafts with pagination and filters."""
        stmt = select(ArticleDraftModel)
        count_stmt = select(ArticleDraftModel.id)

        # Apply filters
        if account_id:
            stmt = stmt.where(ArticleDraftModel.account_id == account_id)
            count_stmt = count_stmt.where(ArticleDraftModel.account_id == account_id)
        if draft_status:
            stmt = stmt.where(ArticleDraftModel.draft_status == draft_status)
            count_stmt = count_stmt.where(ArticleDraftModel.draft_status == draft_status)
        if publish_status:
            stmt = stmt.where(ArticleDraftModel.publish_status == publish_status)
            count_stmt = count_stmt.where(ArticleDraftModel.publish_status == publish_status)

        # Count
        count_result = await db.execute(
            select(sa_func.count()).select_from(count_stmt.subquery())
        )
        total = count_result.scalar() or 0

        # Paginate
        stmt = stmt.order_by(desc(ArticleDraftModel.updated_at), desc(ArticleDraftModel.id))
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await db.execute(stmt)
        drafts = list(result.scalars().all())

        logger.info(
            "draft_list_loaded",
            account_id=account_id,
            draft_status=draft_status,
            publish_status=publish_status,
            page=page,
            page_size=page_size,
            returned=len(drafts),
            total=total,
        )

        return drafts, total

    async def confirm_publish(
        self, draft_id: int, db: AsyncSession, confirmed_by: str = "user"
    ) -> ArticleDraftModel:
        """
        Confirm draft publish.

        State transition: pending_review -> approved -> published
        Or: draft -> approved -> published

        Args:
            draft_id: The draft ID
            db: Database session
            confirmed_by: Who confirmed (default: 'user')

        Returns:
            Updated ArticleDraftModel
        """
        draft = await self.get_draft(draft_id, db)

        # Cannot confirm if already published
        if draft.publish_status == "published":
            raise DraftAlreadyPublishedError(draft_id)

        # Validate state transition
        if draft.draft_status not in {"pending_review", "draft"}:
            raise DraftInvalidStatusError(draft_id, draft.draft_status, "confirm-publish")

        # Confirm only moves the draft into the approved state.
        # Real WeChat publish happens in the dedicated publish pipeline.
        draft.draft_status = "approved"
        if draft.publish_status == "failed":
            draft.publish_status = "not_published"
        draft.confirmed_at = datetime.now(timezone.utc)
        draft.confirmed_by = confirmed_by
        draft.published_at = None

        db.add(draft)
        await db.flush()
        logger.info(
            "draft_confirmed_for_publish",
            draft_id=draft_id,
            confirmed_by=confirmed_by
        )

        return draft

    async def publish_to_wechat(
        self,
        draft_id: int,
        db: AsyncSession,
        confirmed_by: str = "user",
        source_mode: str = "manual",
        trigger_type: str = "manual_confirm",
        existing_record_id: int | None = None,
    ) -> tuple[ArticleDraftModel, dict]:
        """Compatibility wrapper around the dedicated WeChat publish service."""
        from app.services.wechat_publish_service import wechat_publish_service

        result = await wechat_publish_service.publish_draft_to_wechat(
            draft_id,
            operator=confirmed_by,
            source_mode=source_mode,
            trigger_type=trigger_type,
            existing_record_id=existing_record_id,
            db=db,
        )
        draft = await self.get_draft(draft_id, db)
        return draft, {
            "success": result.success,
            "publish_record_id": result.publish_record_id,
            "media_id": result.wechat_draft_media_id,
            "publish_id": result.wechat_publish_id,
            "url": result.wechat_article_url,
            "publish_status": result.publish_status,
            "decision": result.decision,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "simulated": result.simulated,
            "simulation_source": result.simulation_source,
            "provider": result.provider,
        }

    async def _handle_publish_failure(
        self,
        record_id: int,
        draft: ArticleDraftModel,
        db: AsyncSession,
        error_code: str,
        error_message: str,
    ):
        """Handle publish failure - update record and draft."""
        from app.services.publish_record_service import publish_record_service

        # Update publish record
        await publish_record_service.update_failed(
            record_id=record_id,
            db=db,
            error_code=error_code,
            error_message=error_message,
            response_snapshot=f"failed: {error_code} - {error_message[:100]}",
        )

        # Update draft status
        draft.publish_status = "failed"
        draft.publish_error_message = f"[{error_code}] {error_message[:200]}"
        db.add(draft)
        await db.flush()

        # Sync account publish status
        if draft.account_id:
            await self._sync_account_publish_status(draft.account_id, db, "failed", error_message[:200])

        logger.warning(
            "draft_wechat_publish_failed",
            draft_id=draft.id,
            record_id=record_id,
            error_code=error_code,
            error_message=error_message
        )

    async def _sync_account_publish_status(
        self,
        account_id: str,
        db: AsyncSession,
        status: str,
        error_message: str | None = None,
    ):
        """Sync publish status to account."""
        from app.models.tables import AccountModel
        from sqlalchemy import update

        update_data = {
            "last_publish_status": status,
        }
        if error_message:
            update_data["last_publish_error_message"] = error_message[:500]
        if status == "published":
            update_data["last_published_at"] = datetime.now(timezone.utc)

        stmt = (
            update(AccountModel)
            .where(AccountModel.id == account_id)
            .values(**update_data)
        )
        await db.execute(stmt)
        await db.flush()

        logger.info(
            "account_publish_status_synced",
            account_id=account_id,
            status=status
        )

    async def retry_publish_to_wechat(
        self,
        draft_id: int,
        db: AsyncSession,
        confirmed_by: str = "user",
    ) -> tuple[ArticleDraftModel, dict]:
        """
        Retry failed publish for a draft.

        Args:
            draft_id: The draft ID
            db: Database session
            confirmed_by: Who triggered retry (default: 'user')

        Returns:
            Tuple of (updated_draft, publish_result)

        Raises:
            PublishDecisionError: If validation fails
            PublishRecordError: If no failed record found or max retries exceeded
        """
        from app.services.publish_decision_service import publish_decision_service, PublishDecisionError
        from app.services.publish_record_service import publish_record_service, PublishRecordError
        from app.core.exceptions import DraftPublishError

        # Get latest record to check status
        latest = await publish_record_service.get_latest_for_draft(draft_id, db)

        if not latest:
            raise PublishRecordError(f"No publish record found for draft {draft_id}")

        # Check if retry is allowed
        if latest.publish_status not in {"failed", "unknown"}:
            raise PublishRecordError(
                f"Cannot retry: latest publish status is '{latest.publish_status}', "
                f"expected 'failed' or 'unknown'"
            )

        if latest.retry_count >= 3:
            raise PublishRecordError(
                f"Cannot retry: maximum retry attempts (3) exceeded. "
                f"Please create a new draft instead."
            )

        # Create new retry record (this will be the record we use)
        try:
            new_record = await publish_record_service.increment_retry(
                record_id=latest.id,
                db=db,
            )
        except PublishRecordError:
            raise

        # Get account for source_mode
        from app.models.tables import AccountModel
        stmt = select(AccountModel).where(AccountModel.id == latest.account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        source_mode = account.operation_mode if account else latest.source_mode

        # Publish with the new record ID (existing_record_id)
        return await self.publish_to_wechat(
            draft_id=draft_id,
            db=db,
            confirmed_by=confirmed_by,
            source_mode=source_mode,
            trigger_type="manual_retry",
            existing_record_id=new_record.id,
        )

    def _markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to basic HTML for WeChat."""
        if not markdown:
            return ""
        # Simple conversion - in production, use a proper markdown library
        import re
        html = markdown
        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        # Paragraphs
        html = re.sub(r'\n\n', '</p><p>', html)
        html = f'<p>{html}</p>'
        return html

    async def get_wechat_publish_record(
        self,
        draft_id: int,
        db: AsyncSession
    ) -> WeChatPublishRecordModel | None:
        """Get WeChat publish record for a draft."""
        stmt = (
            select(WeChatPublishRecordModel)
            .where(WeChatPublishRecordModel.draft_id == draft_id)
            .order_by(
                desc(WeChatPublishRecordModel.created_at),
                desc(WeChatPublishRecordModel.id),
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def discard_draft(
        self, draft_id: int, db: AsyncSession
    ) -> ArticleDraftModel:
        """
        Discard a draft.

        State transition: pending_review -> discarded
        Or: draft -> discarded

        Terminal states (published, discarded, rejected) cannot be discarded.

        Args:
            draft_id: The draft ID
            db: Database session

        Returns:
            Updated ArticleDraftModel
        """
        draft = await self.get_draft(draft_id, db)

        # Cannot discard terminal states
        if draft.draft_status in {"discarded", "rejected", "published"}:
            raise DraftInvalidStatusError(draft_id, draft.draft_status, "discard")
        if draft.publish_status == "published":
            raise DraftInvalidStatusError(draft_id, draft.draft_status, "discard")

        # Update draft status
        draft.draft_status = "discarded"
        db.add(draft)
        await db.flush()
        logger.info("draft_discarded", draft_id=draft_id)

        return draft

    async def reject_draft(
        self, draft_id: int, db: AsyncSession
    ) -> ArticleDraftModel:
        """
        Reject a draft.

        State transition: pending_review -> rejected

        Args:
            draft_id: The draft ID
            db: Database session

        Returns:
            Updated ArticleDraftModel
        """
        draft = await self.get_draft(draft_id, db)

        # Can only reject from pending_review
        if draft.draft_status != "pending_review":
            raise DraftInvalidStatusError(draft_id, draft.draft_status, "reject")

        # Update draft status
        draft.draft_status = "rejected"
        db.add(draft)
        await db.flush()
        logger.info("draft_rejected", draft_id=draft_id)

        return draft

    async def rerun_from_draft(
        self, draft_id: int, db: AsyncSession
    ) -> tuple[ArticleDraftModel, TaskModel]:
        """
        Create a new task based on the draft's account and positioning.

        Terminal states (discarded, rejected, published) cannot be rerun.

        Args:
            draft_id: The draft ID
            db: Database session

        Returns:
            Tuple of (original_draft, new_task)
        """
        draft = await self.get_draft(draft_id, db)

        # Cannot rerun from terminal states
        if draft.draft_status in {"discarded", "rejected"}:
            raise DraftInvalidStatusError(draft_id, draft.draft_status, "rerun")
        if draft.publish_status == "published":
            raise DraftAlreadyPublishedError(draft_id)

        # Must have an account to rerun
        if not draft.account_id:
            raise DraftCreateError(
                draft.task_id,
                "draft has no account_id, cannot rerun"
            )

        # Get account positioning
        stmt = select(AccountModel).where(AccountModel.id == draft.account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            raise DraftCreateError(
                draft.task_id,
                f"account {draft.account_id} not found"
            )

        # Create new task with same positioning
        task_id = generate_task_id()
        task = TaskModel(
            id=task_id,
            account_id=draft.account_id,
            workflow_id="default_pipeline",
            status="pending",
            input_data={"positioning": account.positioning},
        )
        db.add(task)
        await db.flush()
        logger.info(
            "draft_rerun_created",
            draft_id=draft_id,
            original_task_id=draft.task_id,
            new_task_id=task_id,
            account_id=draft.account_id
        )

        return draft, task

    async def get_pending_review_count(
        self, db: AsyncSession, account_id: str | None = None
    ) -> int:
        """Get count of pending review drafts."""
        stmt = select(sa_func.count()).select_from(ArticleDraftModel).where(
            ArticleDraftModel.draft_status == "pending_review"
        )
        if account_id:
            stmt = stmt.where(ArticleDraftModel.account_id == account_id)
        result = await db.execute(stmt)
        count = result.scalar() or 0
        logger.info("draft_pending_review_count_loaded", account_id=account_id, count=count)
        return count


draft_service = DraftService()
