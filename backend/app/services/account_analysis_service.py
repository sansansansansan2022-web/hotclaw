"""Account-level insight snapshots for pre-generation decisions."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.tracer import generate_analysis_snapshot_id
from app.models.tables import AccountAnalysisSnapshotModel, ArticleDraftModel
from app.services.account_service import account_service
from app.services.query_planner_service import query_planner_service

logger = get_logger(__name__)


class AccountAnalysisService:
    """Build and persist account-level insight snapshots."""

    async def get_latest_snapshot(
        self,
        account_id: str,
        db: AsyncSession,
    ) -> AccountAnalysisSnapshotModel | None:
        result = await db.execute(
            select(AccountAnalysisSnapshotModel)
            .where(AccountAnalysisSnapshotModel.account_id == account_id)
            .order_by(
                desc(AccountAnalysisSnapshotModel.generated_at),
                desc(AccountAnalysisSnapshotModel.created_at),
                desc(AccountAnalysisSnapshotModel.id),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_or_refresh_snapshot(
        self,
        account_id: str,
        db: AsyncSession,
    ) -> AccountAnalysisSnapshotModel:
        snapshot = await self.get_latest_snapshot(account_id, db)
        if snapshot is not None:
            return snapshot
        return await self.refresh_snapshot(account_id, db)

    async def refresh_snapshot(
        self,
        account_id: str,
        db: AsyncSession,
    ) -> AccountAnalysisSnapshotModel:
        detail = await account_service.get_account_detail(account_id, db)
        account_context = await account_service.get_account_context(account_id, db) or {}
        recent_drafts = await self._list_recent_drafts(account_id, db)
        latest_ops_context = detail.get("latest_ops_context") if isinstance(detail, dict) else {}
        latest_ops_context = latest_ops_context if isinstance(latest_ops_context, dict) else {}

        query_plan = query_planner_service.build_plan(
            profile={
                "positioning_raw": detail.get("positioning") or "",
                "target_audience": detail.get("audience") or "",
                "tone": detail.get("tone_style") or "",
            },
            account_context=account_context,
            ops_context=latest_ops_context,
        )

        content_lanes = self._build_content_lanes(query_plan, latest_ops_context, recent_drafts)
        style_keywords = self._build_style_keywords(detail, account_context)
        banned_angles = self._dedupe_strings(query_plan.get("banned_angles") or [])
        recent_topics = self._build_recent_topics(recent_drafts)
        reference_overview = self._build_reference_overview(account_context.get("reference_sources") or [])
        latest_ops_summary = self._build_latest_ops_summary(detail, latest_ops_context, recent_topics)

        snapshot = AccountAnalysisSnapshotModel(
            id=generate_analysis_snapshot_id(),
            account_id=account_id,
            positioning_summary=self._build_positioning_summary(detail, query_plan),
            audience_summary=self._clip_text(
                detail.get("audience")
                or (detail.get("latest_ops_context") or {}).get("account_health", {}).get("status")
                or "Audience profile is still being inferred from account positioning and recent activity.",
                240,
            ),
            tone_summary=self._clip_text(
                detail.get("tone_style")
                or "Professional and account-fit tone inferred from current account setup and references.",
                180,
            ),
            content_lanes_json=content_lanes,
            style_keywords_json=style_keywords,
            banned_angles_json=banned_angles,
            recent_topics_json=recent_topics,
            reference_overview_json=reference_overview,
            latest_ops_summary_json=latest_ops_summary,
            status=str(latest_ops_summary.get("status") or "ready"),
        )
        db.add(snapshot)
        await db.flush()
        logger.info(
            "account_insight_refreshed",
            account_id=account_id,
            snapshot_id=snapshot.id,
            content_lane_count=len(content_lanes),
            reference_count=len(reference_overview),
            recent_topic_count=len(recent_topics),
        )
        return snapshot

    def serialize_snapshot(self, snapshot: AccountAnalysisSnapshotModel) -> dict[str, Any]:
        reference_items = snapshot.reference_overview_json or []
        operations = snapshot.latest_ops_summary_json if isinstance(snapshot.latest_ops_summary_json, dict) else {}
        return {
            "id": snapshot.id,
            "account_id": snapshot.account_id,
            "status": snapshot.status,
            "profile": {
                "positioning_summary": snapshot.positioning_summary,
                "audience_summary": snapshot.audience_summary,
                "tone_summary": snapshot.tone_summary,
                "style_keywords": snapshot.style_keywords_json or [],
                "banned_angles": snapshot.banned_angles_json or [],
            },
            "content_strategy": {
                "content_lanes": snapshot.content_lanes_json or [],
                "recent_topics": snapshot.recent_topics_json or [],
            },
            "references": {
                "total": len(reference_items),
                "items": reference_items,
            },
            "operations": {
                "status": str(operations.get("status") or snapshot.status or "ready"),
                "effective_mode": operations.get("effective_mode"),
                "requested_mode": operations.get("requested_mode"),
                "allow_auto_publish": operations.get("allow_auto_publish"),
                "preferred_content_lane": operations.get("preferred_content_lane"),
                "pending_review_count": operations.get("pending_review_count"),
                "recent_failed_publish_count": operations.get("recent_failed_publish_count"),
                "recent_failed_task_count": operations.get("recent_failed_task_count"),
                "ops_notes": operations.get("ops_notes") or [],
                "risk_alerts": operations.get("risk_alerts") or [],
            },
            "generated_at": snapshot.generated_at,
            "created_at": snapshot.created_at,
            "updated_at": snapshot.updated_at,
        }

    async def _list_recent_drafts(
        self,
        account_id: str,
        db: AsyncSession,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(
                ArticleDraftModel.id,
                ArticleDraftModel.title,
                ArticleDraftModel.selected_topic,
                ArticleDraftModel.draft_status,
                ArticleDraftModel.updated_at,
                ArticleDraftModel.summary,
            )
            .where(ArticleDraftModel.account_id == account_id)
            .order_by(desc(ArticleDraftModel.updated_at), desc(ArticleDraftModel.id))
            .limit(limit)
        )
        rows = []
        for row in result.all():
            rows.append(
                {
                    "id": row.id,
                    "title": row.title,
                    "selected_topic": row.selected_topic,
                    "draft_status": row.draft_status,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "summary": row.summary,
                }
            )
        return rows

    def _build_positioning_summary(self, detail: dict[str, Any], query_plan: dict[str, Any]) -> str:
        positioning = self._clip_text(detail.get("positioning") or "", 180)
        lane = ((query_plan.get("lane") or {}).get("label")) or "通用洞察"
        audience = self._clip_text(detail.get("audience") or "", 80)
        if audience:
            return f"{positioning} Current strongest content lane: {lane}. Core audience focus: {audience}."
        return f"{positioning} Current strongest content lane: {lane}."

    def _build_content_lanes(
        self,
        query_plan: dict[str, Any],
        latest_ops_context: dict[str, Any],
        recent_drafts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        lanes: list[dict[str, Any]] = []
        primary_lane = query_plan.get("lane") if isinstance(query_plan.get("lane"), dict) else {}
        if primary_lane:
            lanes.append(
                {
                    "lane_id": str(primary_lane.get("id") or "general_insight"),
                    "label": str(primary_lane.get("label") or "通用洞察"),
                    "reason": str(primary_lane.get("reason") or "Inferred from account positioning and strategy."),
                    "priority": "primary",
                }
            )

        preferred_lane = ((latest_ops_context.get("run_strategy") or {}).get("preferred_content_lane") or "").strip()
        if preferred_lane and preferred_lane not in {item["label"] for item in lanes}:
            lanes.append(
                {
                    "lane_id": self._slugify(preferred_lane),
                    "label": preferred_lane,
                    "reason": "Preferred by the latest ops strategy snapshot.",
                    "priority": "secondary",
                }
            )

        topic_counter = Counter()
        for item in recent_drafts:
            for token in self._extract_keywords(str(item.get("selected_topic") or item.get("title") or "")):
                topic_counter[token] += 1
        for token, _ in topic_counter.most_common(2):
            if token in {item["label"] for item in lanes}:
                continue
            lanes.append(
                {
                    "lane_id": self._slugify(token),
                    "label": token,
                    "reason": "Repeated in recent drafts and likely still belongs in the content lane mix.",
                    "priority": "secondary",
                }
            )
        return lanes[:4]

    def _build_style_keywords(
        self,
        detail: dict[str, Any],
        account_context: dict[str, Any],
    ) -> list[str]:
        candidates: list[str] = []
        candidates.extend(self._extract_keywords(str(detail.get("tone_style") or "")))
        candidates.extend(self._extract_keywords(str(detail.get("content_strategy") or "")))
        style_guide = account_context.get("reference_style_guide") or {}
        if isinstance(style_guide, dict):
            for item in style_guide.get("style_takeaways") or []:
                candidates.extend(self._extract_keywords(str(item)))
        if not candidates:
            candidates = ["专业", "清晰", "可执行"]
        return self._dedupe_strings(candidates)[:10]

    def _build_recent_topics(self, recent_drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        topics: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in recent_drafts:
            title = str(item.get("selected_topic") or item.get("title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            topics.append(
                {
                    "title": title,
                    "source": "recent_draft",
                    "status": item.get("draft_status"),
                    "created_at": item.get("updated_at"),
                }
            )
        return topics[:6]

    def _build_reference_overview(self, reference_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        overview: list[dict[str, Any]] = []
        for item in reference_sources:
            if not isinstance(item, dict):
                continue
            overview.append(
                {
                    "id": str(item.get("id") or ""),
                    "name": item.get("name") or "Reference source",
                    "source_type": item.get("source_type") or "reference",
                    "sync_status": item.get("sync_status"),
                    "article_count": int(item.get("article_count") or 0),
                    "notes": item.get("notes"),
                    "resolved_title": item.get("resolved_title"),
                    "preview": self._clip_text(item.get("preview"), 180),
                }
            )
        return overview[:6]

    def _build_latest_ops_summary(
        self,
        detail: dict[str, Any],
        latest_ops_context: dict[str, Any],
        recent_topics: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_strategy = latest_ops_context.get("run_strategy") if isinstance(latest_ops_context, dict) else {}
        run_strategy = run_strategy if isinstance(run_strategy, dict) else {}
        signals = latest_ops_context.get("signals") if isinstance(latest_ops_context, dict) else {}
        signals = signals if isinstance(signals, dict) else {}
        ops_notes = latest_ops_context.get("ops_notes") if isinstance(latest_ops_context, dict) else []
        ops_notes = [str(item).strip() for item in ops_notes or [] if str(item).strip()]

        risk_alerts: list[dict[str, Any]] = []
        if len(recent_topics) >= 3:
            repeated_words = Counter(
                token for topic in recent_topics for token in self._extract_keywords(topic.get("title") or "")
            )
            if any(count >= 2 for count in repeated_words.values()):
                risk_alerts.append(
                    {
                        "type": "content_fatigue",
                        "level": "medium",
                        "title": "Content fatigue detected",
                        "message": "Recent drafts are clustering around similar themes. Fresh recommendations should widen the angle.",
                    }
                )
        if detail.get("latest_ops_degraded"):
            risk_alerts.append(
                {
                    "type": "ops_degraded",
                    "level": "medium",
                    "title": "Runtime degraded recently",
                    "message": "Latest operations snapshot shows the effective mode was downgraded during recent runs.",
                }
            )
        if bool(detail.get("publish_paused")):
            risk_alerts.append(
                {
                    "type": "publish_paused",
                    "level": "high",
                    "title": "Publish is paused",
                    "message": "Draft creation can continue, but publishing is currently paused for this account.",
                }
            )

        status = str((latest_ops_context.get("account_health") or {}).get("status") or "ready")
        return {
            "status": status,
            "effective_mode": run_strategy.get("effective_mode"),
            "requested_mode": run_strategy.get("requested_mode"),
            "allow_auto_publish": run_strategy.get("allow_auto_publish"),
            "preferred_content_lane": run_strategy.get("preferred_content_lane"),
            "pending_review_count": signals.get("pending_review_count"),
            "recent_failed_publish_count": signals.get("recent_failed_publish_count"),
            "recent_failed_task_count": signals.get("recent_failed_task_count"),
            "ops_notes": ops_notes,
            "risk_alerts": risk_alerts,
        }

    def _extract_keywords(self, text: str) -> list[str]:
        normalized = re.sub(r"[\r\n\t,/|]+", " ", text or "")
        parts = re.split(r"[\s，。；：、“”‘’!！?？()\[\]{}]+", normalized)
        keywords: list[str] = []
        for part in parts:
            token = str(part).strip(" -_")
            if len(token) < 2:
                continue
            if token.lower() in {"the", "and", "with", "for", "from", "that", "this"}:
                continue
            keywords.append(token)
        return keywords

    def _dedupe_strings(self, values: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _clip_text(self, value: Any, limit: int) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return text[:limit] + ("..." if len(text) > limit else "")

    def _slugify(self, value: str) -> str:
        text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", value.strip().lower())
        return text.strip("_") or "lane"


account_analysis_service = AccountAnalysisService()
