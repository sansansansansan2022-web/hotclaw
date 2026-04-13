"""Recommendation generation for account-scoped content discovery."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.tracer import generate_recommendation_id, generate_workspace_id
from app.models.tables import RecommendedContentItemModel
from app.services.account_analysis_service import account_analysis_service
from app.services.account_service import account_service
from app.services.query_planner_service import query_planner_service
from app.skills.registry import skill_registry
from app.skills.services.skill_router_service import skill_router_service
from app.skills.services.skill_runtime_service import skill_runtime_service

logger = get_logger(__name__)


class RecommendationService:
    """Build account-fit recommended content items before formal generation."""

    async def list_recommendations(
        self,
        account_id: str,
        db: AsyncSession,
        *,
        source_type: str | None = None,
        sort_by: str = "relevance",
        status: str | None = None,
    ) -> tuple[list[RecommendedContentItemModel], int, datetime | None]:
        stmt = select(RecommendedContentItemModel).where(RecommendedContentItemModel.account_id == account_id)
        count_stmt = select(sa_func.count()).select_from(RecommendedContentItemModel).where(
            RecommendedContentItemModel.account_id == account_id
        )

        if source_type:
            stmt = stmt.where(RecommendedContentItemModel.source_type == source_type)
            count_stmt = count_stmt.where(RecommendedContentItemModel.source_type == source_type)
        if status:
            stmt = stmt.where(RecommendedContentItemModel.status == status)
            count_stmt = count_stmt.where(RecommendedContentItemModel.status == status)

        if sort_by == "freshness":
            stmt = stmt.order_by(
                desc(RecommendedContentItemModel.freshness_score),
                desc(RecommendedContentItemModel.updated_at),
            )
        else:
            stmt = stmt.order_by(
                desc(RecommendedContentItemModel.relevance_score),
                desc(RecommendedContentItemModel.authority_score),
                desc(RecommendedContentItemModel.updated_at),
            )

        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        total_result = await db.execute(count_stmt)
        refreshed_at = max((row.updated_at for row in rows if row.updated_at), default=None)
        return rows, int(total_result.scalar() or 0), refreshed_at

    async def refresh_recommendations(
        self,
        account_id: str,
        db: AsyncSession,
    ) -> list[RecommendedContentItemModel]:
        snapshot = await account_analysis_service.get_or_refresh_snapshot(account_id, db)
        account_context = await account_service.get_account_context(account_id, db) or {}
        query_plan = query_planner_service.build_plan(
            profile={
                "positioning_raw": snapshot.positioning_summary,
                "target_audience": snapshot.audience_summary or "",
                "tone": snapshot.tone_summary or "",
                "source_preferences": self._infer_source_preferences(snapshot),
                "research_mode": self._infer_research_mode(snapshot),
                "open_source_mode": self._infer_open_source_mode(snapshot),
            },
            account_context=account_context,
            ops_context={
                "run_strategy": {
                    "preferred_content_lane": (snapshot.latest_ops_summary_json or {}).get("preferred_content_lane"),
                }
            },
        )

        recommendations: list[dict[str, Any]] = []
        recommendations.extend(await self._collect_hot_topic_recommendations(query_plan))
        recommendations.extend(
            await self._collect_skill_recommendations(
                account_id=account_id,
                snapshot=snapshot,
                account_context=account_context,
                query_plan=query_plan,
                db=db,
            )
        )

        rows = await self._upsert_recommendations(account_id, recommendations, db)
        logger.info(
            "recommendation_refresh_completed",
            account_id=account_id,
            recommendation_count=len(rows),
            source_types=sorted({row.source_type for row in rows}),
        )
        return rows

    def serialize_item(self, row: RecommendedContentItemModel) -> dict[str, Any]:
        relevance = float(row.relevance_score or 0.0)
        authority = float(row.authority_score or 0.0)
        freshness = float(row.freshness_score or 0.0)
        return {
            "id": row.id,
            "account_id": row.account_id,
            "title": row.title,
            "summary": row.summary,
            "source": {
                "source_type": row.source_type,
                "source_name": row.source_name,
                "source_url": row.source_url,
                "published_at": row.published_at,
            },
            "scores": {
                "relevance": row.relevance_score,
                "authority": row.authority_score,
                "freshness": row.freshness_score,
                "overall": round((relevance + authority + freshness) / 3, 4),
            },
            "rationale": {
                "reason": row.reason,
                "evidence_points": self._build_evidence_points(row),
            },
            "topic_tags": row.topic_tags_json or [],
            "risk_flags": self._build_risk_flags(row),
            "status": row.status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def build_list_summary(self, rows: list[RecommendedContentItemModel]) -> dict[str, dict[str, int]]:
        source_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for row in rows:
            source_key = str(row.source_type or "external")
            status_key = str(row.status or "new")
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
        return {
            "source_counts": source_counts,
            "status_counts": status_counts,
        }

    async def _collect_hot_topic_recommendations(self, query_plan: dict[str, Any]) -> list[dict[str, Any]]:
        skill = skill_registry.get("hot_topic_fetch_skill")
        response = await skill.execute(
            {
                "queries": query_plan.get("primary_queries") or query_plan.get("secondary_queries") or [],
                "keywords": query_plan.get("search_terms") or [],
                "engines": ["weixin", "sogou", "360"],
                "max_results_per_engine": 6,
            }
        )
        if response.get("status") != "success":
            logger.warning("hot_topic_recommendation_fetch_failed", error=response.get("error"))
            return []

        lane_label = ((query_plan.get("lane") or {}).get("label")) or "内容洞察"
        rows: list[dict[str, Any]] = []
        for item in (response.get("data") or {}).get("results") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            rows.append(
                {
                    "title": title,
                    "summary": str(item.get("snippet") or title).strip(),
                    "source_type": str(item.get("source_type") or "search_result"),
                    "source_name": str(item.get("source") or "Public Search").strip(),
                    "source_url": str(item.get("url") or "").strip() or None,
                    "published_at": None,
                    "relevance_score": 0.62,
                    "authority_score": 0.45 if item.get("source_type") == "weixin" else 0.35,
                    "freshness_score": 0.78,
                    "reason": f"Matches the current {lane_label} lane and source-scout queries.",
                    "topic_tags_json": self._dedupe_strings(
                        [lane_label, *[str(term) for term in query_plan.get("search_terms") or []]]
                    )[:5],
                    "source_payload_json": item,
                }
            )
        return rows

    async def _collect_skill_recommendations(
        self,
        *,
        account_id: str,
        snapshot,
        account_context: dict[str, Any],
        query_plan: dict[str, Any],
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        profile = {
            "positioning_raw": snapshot.positioning_summary,
            "domain": ((query_plan.get("lane") or {}).get("label")) or "",
            "subdomain": snapshot.content_lanes_json[0]["label"] if snapshot.content_lanes_json else "",
            "source_preferences": self._infer_source_preferences(snapshot),
            "research_mode": self._infer_research_mode(snapshot),
            "open_source_mode": self._infer_open_source_mode(snapshot),
        }
        plans = skill_router_service.plan_invocations(
            profile=profile,
            task_goal=snapshot.positioning_summary,
            current_node="hot_topic_analysis",
            workspace_context={},
            account_context=account_context,
        )
        if not plans:
            return []

        workspace_id = generate_workspace_id()
        task_id = f"rec_{account_id}"
        rows: list[dict[str, Any]] = []
        for plan in plans:
            invocation = await skill_runtime_service.invoke(
                skill_name=plan["skill_name"],
                input_data=plan["input_data"],
                db=db,
                task_id=task_id,
                workspace_id=workspace_id,
                account_id=account_id,
            )
            results = (invocation.get("data") or {}).get("results") or []
            if plan["skill_name"] == "github_project_curator_skill":
                rows.extend(self._map_github_results(results))
            elif plan["skill_name"] == "scholar_paper_search_skill":
                rows.extend(self._map_scholar_results(results))
        return rows

    async def _upsert_recommendations(
        self,
        account_id: str,
        items: list[dict[str, Any]],
        db: AsyncSession,
    ) -> list[RecommendedContentItemModel]:
        result = await db.execute(
            select(RecommendedContentItemModel)
            .where(RecommendedContentItemModel.account_id == account_id)
            .order_by(desc(RecommendedContentItemModel.updated_at), desc(RecommendedContentItemModel.id))
        )
        existing_rows = list(result.scalars().all())
        existing_by_key = {self._fingerprint_model(row): row for row in existing_rows}
        incoming_keys: set[str] = set()
        touched: list[RecommendedContentItemModel] = []

        for item in items:
            key = self._fingerprint_payload(item)
            if not key:
                continue
            incoming_keys.add(key)
            row = existing_by_key.get(key)
            if row is None:
                row = RecommendedContentItemModel(
                    id=generate_recommendation_id(),
                    account_id=account_id,
                    status="new",
                )
                db.add(row)
            row.title = str(item.get("title") or "").strip()
            row.summary = str(item.get("summary") or "").strip() or None
            row.source_type = str(item.get("source_type") or "external").strip()
            row.source_name = str(item.get("source_name") or "").strip() or None
            row.source_url = str(item.get("source_url") or "").strip() or None
            row.published_at = item.get("published_at")
            row.relevance_score = float(item.get("relevance_score") or 0.0)
            row.authority_score = float(item.get("authority_score") or 0.0)
            row.freshness_score = float(item.get("freshness_score") or 0.0)
            row.reason = str(item.get("reason") or "").strip() or None
            row.topic_tags_json = item.get("topic_tags_json") or []
            row.source_payload_json = item.get("source_payload_json") if isinstance(item.get("source_payload_json"), dict) else {}
            touched.append(row)

        for row in existing_rows:
            if self._fingerprint_model(row) in incoming_keys:
                continue
            if row.status == "new":
                await db.delete(row)

        await db.flush()
        touched.sort(
            key=lambda row: (
                float(row.relevance_score or 0.0),
                float(row.authority_score or 0.0),
                float(row.freshness_score or 0.0),
            ),
            reverse=True,
        )
        return touched

    def _map_github_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            score = item.get("score_breakdown") if isinstance(item.get("score_breakdown"), dict) else {}
            published_at = self._parse_datetime(item.get("pushed_at") or item.get("updated_at"))
            mapped.append(
                {
                    "title": item.get("full_name") or item.get("repo_name") or "GitHub project",
                    "summary": item.get("description") or item.get("best_for") or item.get("why_selected") or "",
                    "source_type": "github_repo",
                    "source_name": "GitHub",
                    "source_url": item.get("url"),
                    "published_at": published_at,
                    "relevance_score": float(score.get("topic_relevance") or 0.0),
                    "authority_score": float(score.get("engineering_quality") or 0.0),
                    "freshness_score": float(score.get("maintenance") or 0.0),
                    "reason": item.get("why_selected") or item.get("best_for") or "",
                    "topic_tags_json": self._dedupe_strings(
                        [item.get("category")] + list(item.get("topics") or [])
                    )[:6],
                    "source_payload_json": item,
                }
            )
        return mapped

    def _map_scholar_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            score = item.get("score_breakdown") if isinstance(item.get("score_breakdown"), dict) else {}
            published_at = None
            year = item.get("year")
            if isinstance(year, int) and year > 1900:
                published_at = datetime(year, 1, 1, tzinfo=timezone.utc)
            mapped.append(
                {
                    "title": item.get("title") or "Scholar paper",
                    "summary": item.get("abstract_or_summary") or item.get("why_relevant") or item.get("why_selected") or "",
                    "source_type": "scholar_paper",
                    "source_name": item.get("venue") or "OpenAlex / Crossref",
                    "source_url": item.get("url"),
                    "published_at": published_at,
                    "relevance_score": float(score.get("relevance") or 0.0),
                    "authority_score": float(score.get("venue_quality") or 0.0),
                    "freshness_score": float(score.get("freshness") or 0.0),
                    "reason": item.get("why_selected") or item.get("why_relevant") or "",
                    "topic_tags_json": self._dedupe_strings(
                        [item.get("paper_type"), item.get("venue")]
                    )[:5],
                    "source_payload_json": item,
                }
            )
        return mapped

    def _fingerprint_payload(self, item: dict[str, Any]) -> str:
        return "||".join(
            [
                str(item.get("source_type") or "").strip().lower(),
                str(item.get("source_url") or "").strip().lower(),
                str(item.get("title") or "").strip().lower(),
            ]
        )

    def _fingerprint_model(self, row: RecommendedContentItemModel) -> str:
        return "||".join(
            [
                str(row.source_type or "").strip().lower(),
                str(row.source_url or "").strip().lower(),
                str(row.title or "").strip().lower(),
            ]
        )

    def _infer_source_preferences(self, snapshot) -> list[str]:
        lane_blob = " ".join(
            [
                str(snapshot.positioning_summary or ""),
                str(snapshot.audience_summary or ""),
                str(snapshot.tone_summary or ""),
                " ".join(str(item.get("label") or "") for item in (snapshot.content_lanes_json or [])),
            ]
        ).lower()
        preferences = []
        if any(token in lane_blob for token in ["github", "开源", "repo", "developer", "agent", "tool"]):
            preferences.append("github")
        if any(token in lane_blob for token in ["paper", "research", "论文", "学术", "benchmark", "method"]):
            preferences.append("scholar")
        return preferences

    def _infer_research_mode(self, snapshot) -> str:
        joined = " ".join(
            [str(snapshot.positioning_summary or ""), str(snapshot.audience_summary or ""), str(snapshot.tone_summary or "")]
        ).lower()
        return "enabled" if any(token in joined for token in ["paper", "research", "论文", "学术", "benchmark"]) else "disabled"

    def _infer_open_source_mode(self, snapshot) -> str:
        joined = " ".join(
            [str(snapshot.positioning_summary or ""), str(snapshot.audience_summary or ""), str(snapshot.tone_summary or "")]
        ).lower()
        return "enabled" if any(token in joined for token in ["github", "开源", "repo", "developer", "tool"]) else "disabled"

    def _dedupe_strings(self, values: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _parse_datetime(self, value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None

    def _build_evidence_points(self, row: RecommendedContentItemModel) -> list[str]:
        points: list[str] = []
        if row.reason:
            points.append(str(row.reason))
        if row.source_name:
            points.append(f"Source: {row.source_name}")
        if row.topic_tags_json:
            points.append("Topics: " + ", ".join(str(item) for item in (row.topic_tags_json or [])[:3]))
        if row.published_at:
            points.append(f"Published at: {row.published_at.isoformat()}")
        return points[:4]

    def _build_risk_flags(self, row: RecommendedContentItemModel) -> list[str]:
        flags: list[str] = []
        payload = row.source_payload_json if isinstance(row.source_payload_json, dict) else {}
        raw_flags = payload.get("risk_flags")
        if isinstance(raw_flags, list):
            for item in raw_flags:
                text = str(item).strip()
                if text:
                    flags.append(text)

        freshness = float(row.freshness_score or 0.0)
        authority = float(row.authority_score or 0.0)
        if freshness < 0.35:
            flags.append("stale_signal")
        if authority < 0.35:
            flags.append("low_authority")
        return self._dedupe_strings(flags)


recommendation_service = RecommendationService()
