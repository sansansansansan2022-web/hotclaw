"""
Publish Service - 发布服务模块（占位实现）

本模块是微信公众号发布的占位服务，用于未来真实发布集成。

当前策略（MVP 阶段）：
- confirm_publish 在 draft_service 中直接标记草稿为已发布
- 设置 published_at 为当前时间戳
- 模拟成功发布以便快速验证流程

未来集成点：
- 真实的微信 API 调用
- OAuth Token 管理
- 媒体素材上传
- 草稿发布接口调用
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
