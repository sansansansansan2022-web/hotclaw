"""Draft service: business logic for draft lifecycle management."""

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
        # Extract content from result_data
        content = result_data.get("content", {})
        titles = result_data.get("titles", {})
        topics = result_data.get("topics", {})
        profile = result_data.get("profile", {})

        # Get selected title and topic
        selected_title = titles.get("selected_title", "Untitled")
        title_candidates = titles.get("candidates", [])
        selected_topic = topics.get("selected_topic", "")
        summary = content.get("summary", "")

        # Extract main content
        main_content = content.get("content_markdown", content.get("content", ""))

        # Determine draft status based on operation mode
        # - full_auto: auto publish, create draft in approved state
        # - semi_auto: pending_review, requires manual confirmation
        # - manual/manual_task: draft, saved as draft without immediate review
        if operation_mode == "full_auto":
            draft_status = "approved"
            publish_review_required = False
            source_type = "semi_auto_task"
            # Auto publish: set published timestamps
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
            content_html=content.get("content_html"),
            word_count=self._count_words(main_content),
            tags=content.get("tags"),
            structure=content.get("structure"),
            draft_status=draft_status,
            publish_status="published" if operation_mode == "full_auto" else "not_published",
            publish_review_required=publish_review_required,
            source_type=source_type,
            # Auto-publish for full_auto mode
            confirmed_at=now if operation_mode == "full_auto" else None,
            confirmed_by="system" if operation_mode == "full_auto" else None,
            published_at=now if operation_mode == "full_auto" else None,
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
            "content_html": draft.content_html,
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
        count_stmt = select(ArticleDraftModel)

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
        stmt = stmt.order_by(desc(ArticleDraftModel.updated_at))
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await db.execute(stmt)
        drafts = list(result.scalars().all())

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

        # Update draft status
        draft.draft_status = "approved"
        draft.publish_status = "published"
        draft.confirmed_at = datetime.now(timezone.utc)
        draft.confirmed_by = confirmed_by
        draft.published_at = datetime.now(timezone.utc)

        db.add(draft)
        await db.flush()
        logger.info(
            "draft_confirmed_published",
            draft_id=draft_id,
            confirmed_by=confirmed_by
        )

        return draft

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
        return result.scalar() or 0


draft_service = DraftService()
