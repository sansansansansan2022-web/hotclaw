"""Publish service: placeholder for real WeChat official account publishing.

This module is a placeholder for future real publishing integration.

Current strategy:
- confirm_publish in draft_service marks draft as 'published' directly
- published_at is set to current time
- This simulates successful publishing for MVP

Future integration points:
- Real WeChat API calls
- OAuth token management
- Media upload
- Draft publishing
"""

from datetime import datetime, timezone

from app.core.logger import get_logger
from app.models.tables import ArticleDraftModel

logger = get_logger(__name__)


class PublishService:
    """
    Placeholder service for WeChat official account publishing.

    本轮不实现真实发布，仅记录发布状态。
    未来可在此处扩展真实发布逻辑。
    """

    async def publish_draft(self, draft: ArticleDraftModel) -> dict:
        """
        Publish a draft to WeChat official account.

        Current implementation:
        - Simulates successful publishing
        - Sets published_at timestamp

        Future implementation should:
        - Authenticate with WeChat API
        - Upload media
        - Publish article
        - Return real publish result
        """
        logger.info("simulated_publish", draft_id=draft.id, title=draft.title)

        return {
            "success": True,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
            "message": "This is a simulated publish. Real WeChat API integration pending."
        }


publish_service = PublishService()
