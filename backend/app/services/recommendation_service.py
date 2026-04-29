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
from app.services.news_source_service import news_source_service
from app.services.query_planner_service import query_planner_service
from app.skills.registry import skill_registry
from app.skills.services.skill_router_service import skill_router_service
from app.skills.services.skill_runtime_service import skill_runtime_service

logger = get_logger(__name__)

ALLOWED_MIN_RECOMMENDATION_COUNTS = {5, 8, 10}


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
    ) -> tuple[list[RecommendedContentItemModel], int, datetime | None, dict[str, Any]]:
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
        diagnostics = await self._load_latest_diagnostics(
            account_id=account_id,
            db=db,
            rows=rows,
            filtered_view=bool(source_type or status),
        )
        return rows, int(total_result.scalar() or 0), refreshed_at, diagnostics

    async def refresh_recommendations(
        self,
        account_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
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
        source_diagnostics: list[dict[str, Any]] = []

        hot_topic_rows, hot_topic_diagnostics = await self._collect_hot_topic_recommendations(query_plan)
        recommendations.extend(hot_topic_rows)
        source_diagnostics.extend(hot_topic_diagnostics)

        news_rows, news_diagnostics = await news_source_service.collect_candidates(
            snapshot=snapshot,
            query_plan=query_plan,
        )
        recommendations.extend(news_rows)
        source_diagnostics.extend(news_diagnostics)

        skill_rows, skill_diagnostics = await self._collect_skill_recommendations(
            account_id=account_id,
            snapshot=snapshot,
            account_context=account_context,
            query_plan=query_plan,
            db=db,
        )
        recommendations.extend(skill_rows)
        source_diagnostics.extend(skill_diagnostics)

        recommendations = self._rank_account_fit(
            recommendations,
            snapshot=snapshot,
            query_plan=query_plan,
        )

        rows = await self._upsert_recommendations(account_id, recommendations, db)
        diagnostics = self._build_diagnostics_payload(
            rows=rows,
            source_diagnostics=source_diagnostics,
        )
        snapshot.recommendation_diagnostics_json = diagnostics
        snapshot.recommendation_refreshed_at = datetime.now(timezone.utc)
        logger.info(
            "recommendation_refresh_completed",
            account_id=account_id,
            recommendation_count=len(rows),
            source_types=sorted({row.source_type for row in rows}),
            high_relevance_count=diagnostics["filter_diagnostics"]["high_relevance_count"],
            extended_count=diagnostics["filter_diagnostics"]["extended_count"],
        )
        # 在异步上下文中序列化 rows 并分桶（避免懒加载问题）
        serialized_rows = [self.serialize_item(row) for row in rows]
        # 构建 ID 到序列化数据的映射
        serialized_map = {r["id"]: r for r in serialized_rows}
        # 使用分桶逻辑分离高相关性和扩展项
        bucketed = self.bucketize_rows(rows, min_count=5, diagnostics=diagnostics)
        # 返回已序列化的字典，避免在异步上下文中访问 SQLAlchemy 模型属性
        high_relevance_items = [serialized_map.get(row.id) for row in bucketed["high_relevance_items"]]
        extended_items = [serialized_map.get(row.id) for row in bucketed["extended_items"]]
        return {
            "rows": rows,  # 原始行对象（供内部使用）
            "high_relevance_items": high_relevance_items,  # 已序列化的字典列表
            "extended_items": extended_items,  # 已序列化的字典列表
            "serialized_rows": serialized_rows,
            "diagnostics": diagnostics,
            "refreshed_at": snapshot.recommendation_refreshed_at,
        }

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
                "published_at": self._as_utc_datetime(row.published_at),
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

    def _as_utc_datetime(self, value: datetime | None) -> datetime | None:
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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

    def normalize_min_count(self, min_count: int | None) -> int:
        normalized = int(min_count or 5)
        if normalized not in ALLOWED_MIN_RECOMMENDATION_COUNTS:
            raise ValueError("min_count must be one of 5, 8, 10")
        return normalized

    def bucketize_rows(
        self,
        rows: list[RecommendedContentItemModel],
        *,
        min_count: int,
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        requested = self.normalize_min_count(min_count)
        high_relevance_items: list[RecommendedContentItemModel] = []
        extended_items: list[RecommendedContentItemModel] = []
        ranked_rows = sorted(rows, key=self._recommendation_rank_key, reverse=True)
        dynamic_high_bar = self._dynamic_high_relevance_bar(ranked_rows)

        for row in ranked_rows:
            if self._is_high_relevance(row, dynamic_high_bar=dynamic_high_bar):
                high_relevance_items.append(row)
                continue
            if self._is_extended_candidate(row):
                extended_items.append(row)

        promoted_items = self._promote_best_extended_items(
            requested_count=requested,
            high_relevance_items=high_relevance_items,
            extended_items=extended_items,
        )
        if promoted_items:
            promoted_ids = {item.id for item in promoted_items}
            high_relevance_items.extend(promoted_items)
            extended_items = [row for row in extended_items if row.id not in promoted_ids]

        returned_count = len(high_relevance_items) + len(extended_items)
        shortage_count = max(requested - returned_count, 0)
        shortage_notice = self._build_shortage_notice(
            requested_min_count=requested,
            high_relevance_count=len(high_relevance_items),
            extended_count=len(extended_items),
            returned_count=returned_count,
            diagnostics=diagnostics or {},
        )
        coverage = {
            "requested_min_count": requested,
            "high_relevance_count": len(high_relevance_items),
            "extended_count": len(extended_items),
            "returned_count": returned_count,
            "shortage_count": shortage_count,
            "meets_requested_min_count": returned_count >= requested,
            "relaxed_count": len(promoted_items),
        }
        normalized_diagnostics = self._build_diagnostics_payload(
            rows=ranked_rows,
            source_diagnostics=(diagnostics or {}).get("source_diagnostics") or [],
            promoted_high_ids={item.id for item in promoted_items},
        )
        return {
            "min_count": requested,
            "high_relevance_items": high_relevance_items,
            "extended_items": extended_items,
            "coverage": coverage,
            "shortage_notice": shortage_notice,
            "source_diagnostics": normalized_diagnostics["source_diagnostics"],
            "filter_diagnostics": normalized_diagnostics["filter_diagnostics"],
        }

    async def _collect_hot_topic_recommendations(
        self,
        query_plan: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
            error = response.get("error") if isinstance(response, dict) else {}
            return [], [
                {
                    "source_key": "public_search_scout",
                    "label": "Public Search Scout",
                    "source_type": "public_search",
                    "status": "failed",
                    "query": None,
                    "candidate_count": 0,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": str((error or {}).get("code") or "search_fetch_failed"),
                    "error_message": str((error or {}).get("message") or "search fetch failed"),
                    "detail": "Public search scouting failed before recommendation ranking.",
                }
            ]

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
                    "source_type": "public_search",
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
                    "source_payload_json": {
                        **item,
                        "collector": {
                            "source_key": "public_search_scout",
                            "label": "Public Search Scout",
                            "kind": "public_search",
                        },
                    },
                }
            )
        return rows, [
            {
                "source_key": "public_search_scout",
                "label": "Public Search Scout",
                "source_type": "public_search",
                "status": "success" if rows else "empty",
                "query": None,
                "candidate_count": len(rows),
                "high_relevance_count": 0,
                "extended_count": 0,
                "filtered_out_count": 0,
                "error_code": None,
                "error_message": None,
                "detail": None if rows else "Public search queries returned no usable scouting candidates.",
            }
        ]

    async def _collect_skill_recommendations(
        self,
        *,
        account_id: str,
        snapshot,
        account_context: dict[str, Any],
        query_plan: dict[str, Any],
        db: AsyncSession,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
            return [], [
                {
                    "source_key": "skill_router",
                    "label": "External Research Skills",
                    "source_type": "external_skill",
                    "status": "not_applicable",
                    "query": None,
                    "candidate_count": 0,
                    "high_relevance_count": 0,
                    "extended_count": 0,
                    "filtered_out_count": 0,
                    "error_code": "no_skill_plan",
                    "error_message": None,
                    "detail": "No account-fit skill invocation was planned for this recommendation refresh.",
                }
            ]

        workspace_id = generate_workspace_id()
        task_id = f"rec_{account_id}"
        rows: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        for plan in plans:
            skill_name = str(plan["skill_name"])
            query_text = str((plan.get("input_data") or {}).get("topic") or "").strip() or None
            try:
                invocation = await skill_runtime_service.invoke(
                    skill_name=skill_name,
                    input_data=plan["input_data"],
                    db=db,
                    task_id=task_id,
                    workspace_id=workspace_id,
                    account_id=account_id,
                )
                results = (invocation.get("data") or {}).get("results") or []
                if skill_name == "github_project_curator_skill":
                    mapped = self._map_github_results(results)
                elif skill_name == "scholar_paper_search_skill":
                    mapped = self._map_scholar_results(results)
                else:
                    mapped = []
                rows.extend(mapped)
                diagnostics.append(
                    {
                        "source_key": skill_name,
                        "label": skill_name,
                        "source_type": "external_skill",
                        "status": "success" if mapped else "empty",
                        "query": query_text,
                        "candidate_count": len(mapped),
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": None,
                        "error_message": None,
                        "detail": None if mapped else "Skill execution succeeded but returned no usable candidates.",
                    }
                )
            except Exception as exc:
                logger.warning("recommendation_skill_fetch_failed", skill_name=skill_name, error=str(exc))
                diagnostics.append(
                    {
                        "source_key": skill_name,
                        "label": skill_name,
                        "source_type": "external_skill",
                        "status": "failed",
                        "query": query_text,
                        "candidate_count": 0,
                        "high_relevance_count": 0,
                        "extended_count": 0,
                        "filtered_out_count": 0,
                        "error_code": f"{skill_name}_failed",
                        "error_message": str(exc),
                        "detail": "External research skill failed during recommendation refresh.",
                    }
                )
        return rows, diagnostics

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
        touched_ids = [row.id for row in touched if row.id]
        if not touched_ids:
            return []

        refreshed_result = await db.execute(
            select(RecommendedContentItemModel).where(RecommendedContentItemModel.id.in_(touched_ids))
        )
        refreshed_rows = list(refreshed_result.scalars().all())
        refreshed_rows.sort(
            key=lambda row: (
                float(row.relevance_score or 0.0),
                float(row.authority_score or 0.0),
                float(row.freshness_score or 0.0),
            ),
            reverse=True,
        )
        return refreshed_rows

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
                    "source_payload_json": {
                        **item,
                        "collector": {
                            "source_key": "github_project_curator_skill",
                            "label": "GitHub Project Curator",
                            "kind": "external_skill",
                        },
                    },
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
                    "source_payload_json": {
                        **item,
                        "collector": {
                            "source_key": "scholar_paper_search_skill",
                            "label": "Scholar Paper Search",
                            "kind": "external_skill",
                        },
                    },
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

    def _rank_account_fit(
        self,
        items: list[dict[str, Any]],
        *,
        snapshot,
        query_plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        lane = (query_plan.get("lane") or {}) if isinstance(query_plan.get("lane"), dict) else {}
        lane_label = str(lane.get("label") or "").strip()
        search_terms = [str(item).strip() for item in (query_plan.get("search_terms") or []) if str(item).strip()]
        source_preferences = [str(item).strip().lower() for item in (query_plan.get("source_preferences") or []) if str(item).strip()]
        audience_summary = str(getattr(snapshot, "audience_summary", "") or "").strip()
        positioning_summary = str(getattr(snapshot, "positioning_summary", "") or "").strip()
        content_lane_labels = [
            str(item.get("label") or "").strip()
            for item in (getattr(snapshot, "content_lanes_json", None) or [])
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ]
        account_keywords = self._derive_account_fit_keywords(
            positioning_summary=positioning_summary,
            audience_summary=audience_summary,
            lane_label=lane_label,
            lane_labels=content_lane_labels,
            search_terms=search_terms,
        )

        ranked: list[dict[str, Any]] = []
        for item in items:
            text_blob = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("summary") or ""),
                    str(item.get("reason") or ""),
                    " ".join(str(tag) for tag in (item.get("topic_tags_json") or [])),
                ]
            ).lower()
            keyword_hits = sum(1 for keyword in account_keywords if keyword and keyword in text_blob)
            keyword_score = min(keyword_hits / max(len(account_keywords), 1), 1.0) if account_keywords else 0.0

            lane_score = 1.0 if lane_label and lane_label.lower() in text_blob else 0.0
            audience_score = 1.0 if audience_summary and any(token in text_blob for token in self._tokenize_text(audience_summary)) else 0.0
            source_preference_score = self._source_preference_score(
                source_type=str(item.get("source_type") or "").strip().lower(),
                source_preferences=source_preferences,
            )

            account_fit_score = round(
                min(1.0, keyword_score * 0.45 + lane_score * 0.2 + audience_score * 0.15 + source_preference_score * 0.2),
                4,
            )
            current_relevance = float(item.get("relevance_score") or 0.0)
            boosted_relevance = round(min(0.99, current_relevance * 0.7 + account_fit_score * 0.3), 4)
            payload = item.get("source_payload_json") if isinstance(item.get("source_payload_json"), dict) else {}
            item["source_payload_json"] = {
                **payload,
                "account_fit": {
                    "score": account_fit_score,
                    "lane_label": lane_label or None,
                    "source_preferences": source_preferences,
                },
            }
            item["relevance_score"] = boosted_relevance
            item["reason"] = self._compose_ranked_reason(
                original_reason=str(item.get("reason") or "").strip(),
                lane_label=lane_label,
                audience_summary=audience_summary,
                account_fit_score=account_fit_score,
            )
            ranked.append(item)

        ranked.sort(
            key=lambda entry: (
                float(entry.get("relevance_score") or 0.0),
                float(entry.get("authority_score") or 0.0),
                float(entry.get("freshness_score") or 0.0),
            ),
            reverse=True,
        )
        return ranked

    def _derive_account_fit_keywords(
        self,
        *,
        positioning_summary: str,
        audience_summary: str,
        lane_label: str,
        lane_labels: list[str],
        search_terms: list[str],
    ) -> list[str]:
        keywords: list[str] = []
        for blob in [positioning_summary, audience_summary, lane_label, *lane_labels, *search_terms]:
            keywords.extend(self._tokenize_text(blob))
        return self._dedupe_strings(keywords)[:18]

    def _tokenize_text(self, value: str) -> list[str]:
        raw = str(value or "").strip().lower()
        if not raw:
            return []
        separators = [",", ".", ":", ";", "/", "\\", "(", ")", "[", "]", "{", "}", "|", "-", "_", "\n", "\t"]
        for token in separators:
            raw = raw.replace(token, " ")
        parts = [part.strip() for part in raw.split(" ") if len(part.strip()) >= 3]
        return parts

    def _source_preference_score(self, *, source_type: str, source_preferences: list[str]) -> float:
        if not source_preferences:
            return 0.4 if source_type == "news_article" else 0.0
        if source_type == "github_repo" and "github" in source_preferences:
            return 1.0
        if source_type == "scholar_paper" and "scholar" in source_preferences:
            return 1.0
        if source_type == "news_article":
            return 0.75
        if source_type == "public_search":
            return 0.35
        return 0.0

    def _compose_ranked_reason(
        self,
        *,
        original_reason: str,
        lane_label: str,
        audience_summary: str,
        account_fit_score: float,
    ) -> str:
        fragments = []
        if original_reason:
            fragments.append(original_reason.rstrip("."))
        if lane_label:
            fragments.append(f"Aligned with the {lane_label} content lane")
        if audience_summary:
            fragments.append("Matched to the target audience profile")
        if account_fit_score >= 0.8:
            fragments.append("Strong account fit")
        elif account_fit_score >= 0.6:
            fragments.append("Solid account fit")
        return ". ".join(self._dedupe_strings(fragments)).strip()

    def _overall_score(self, row: RecommendedContentItemModel) -> float:
        relevance = float(row.relevance_score or 0.0)
        authority = float(row.authority_score or 0.0)
        freshness = float(row.freshness_score or 0.0)
        return round((relevance + authority + freshness) / 3, 4)

    def _account_fit_score(self, row: RecommendedContentItemModel) -> float:
        payload = row.source_payload_json if isinstance(row.source_payload_json, dict) else {}
        account_fit = payload.get("account_fit") if isinstance(payload.get("account_fit"), dict) else {}
        raw_score = account_fit.get("score")
        if raw_score is None:
            return 0.55
        return float(raw_score or 0.0)

    def _recommendation_quality_score(self, row: RecommendedContentItemModel) -> float:
        relevance = float(row.relevance_score or 0.0)
        authority = float(row.authority_score or 0.0)
        freshness = float(row.freshness_score or 0.0)
        account_fit = self._account_fit_score(row)
        return round(
            relevance * 0.42 + authority * 0.22 + freshness * 0.14 + account_fit * 0.22,
            4,
        )

    def _recommendation_rank_key(self, row: RecommendedContentItemModel) -> tuple[float, float, float, float, float]:
        status_rank = 0.0 if str(row.status or "") == "selected" else 1.0
        activity_time = row.published_at or row.updated_at or row.created_at
        published_ts = row.published_at.timestamp() if isinstance(row.published_at, datetime) else 0.0
        return (
            status_rank,
            self._recency_rank(row),
            published_ts,
            self._recommendation_quality_score(row),
            float(row.freshness_score or 0.0),
        )

    def _recency_rank(self, row: RecommendedContentItemModel) -> float:
        activity_time = row.published_at
        if not isinstance(activity_time, datetime):
            return 0.0
        if activity_time.tzinfo is None:
            activity_time = activity_time.replace(tzinfo=timezone.utc)
        age_hours = max((datetime.now(timezone.utc) - activity_time.astimezone(timezone.utc)).total_seconds() / 3600.0, 0.0)
        if age_hours <= 24:
            return 3.0
        if age_hours <= 48:
            return 2.0
        if age_hours <= 168:
            return 1.0
        return 0.0

    def _dynamic_high_relevance_bar(self, rows: list[RecommendedContentItemModel]) -> float:
        if not rows:
            return 0.72
        best_quality = self._recommendation_quality_score(rows[0])
        return round(max(0.58, min(0.72, best_quality - 0.06)), 4)

    def _is_high_relevance(self, row: RecommendedContentItemModel, *, dynamic_high_bar: float | None = None) -> bool:
        risk_flags = set(self._build_risk_flags(row))
        if "low_authority" in risk_flags and float(row.authority_score or 0.0) < 0.25:
            return False
        threshold = float(dynamic_high_bar if dynamic_high_bar is not None else 0.72)
        return (
            self._recommendation_quality_score(row) >= threshold
            and float(row.relevance_score or 0.0) >= 0.52
            and self._overall_score(row) >= 0.53
            and float(row.authority_score or 0.0) >= 0.32
        )

    def _is_extended_candidate(self, row: RecommendedContentItemModel) -> bool:
        if self._is_high_relevance(row):
            return False
        risk_flags = set(self._build_risk_flags(row))
        if "low_authority" in risk_flags and float(row.authority_score or 0.0) < 0.2:
            return False
        return (
            float(row.relevance_score or 0.0) >= 0.36
            and self._overall_score(row) >= 0.43
            and self._recommendation_quality_score(row) >= 0.46
        )

    def _promote_best_extended_items(
        self,
        *,
        requested_count: int,
        high_relevance_items: list[RecommendedContentItemModel],
        extended_items: list[RecommendedContentItemModel],
    ) -> list[RecommendedContentItemModel]:
        needed = max(int(requested_count) - len(high_relevance_items), 0)
        if needed <= 0 or not extended_items:
            return []
        promotable = [
            row
            for row in extended_items
            if self._recommendation_quality_score(row) >= 0.48
            and float(row.relevance_score or 0.0) >= 0.42
            and self._account_fit_score(row) >= 0.45
            and float(row.authority_score or 0.0) >= 0.28
            and self._overall_score(row) >= 0.48
        ]
        promotable.sort(key=self._recommendation_rank_key, reverse=True)
        return promotable[:needed]

    def _build_shortage_notice(
        self,
        *,
        requested_min_count: int,
        high_relevance_count: int,
        extended_count: int,
        returned_count: int,
        diagnostics: dict[str, Any],
    ) -> dict[str, Any]:
        if high_relevance_count >= requested_min_count:
            return {
                "status": "ok",
                "reason_code": None,
                "message": None,
                "recommended_action": None,
            }
        if returned_count >= requested_min_count:
            return {
                "status": "ok",
                "reason_code": None,
                "message": None,
                "recommended_action": None,
            }
        filter_diagnostics = diagnostics.get("filter_diagnostics") if isinstance(diagnostics, dict) else {}
        source_diagnostics = diagnostics.get("source_diagnostics") if isinstance(diagnostics, dict) else []
        raw_candidate_count = int((filter_diagnostics or {}).get("raw_candidate_count") or returned_count)
        failed_or_disabled = [
            item
            for item in (source_diagnostics or [])
            if str(item.get("status") or "") in {"failed", "disabled"}
        ]
        if raw_candidate_count <= 0 and failed_or_disabled:
            return {
                "status": "insufficient_total",
                "reason_code": "source_fetch_failed_or_unavailable",
                "message": (
                    "No real-time recommendation source produced usable candidates for this account during the latest refresh."
                ),
                "recommended_action": "Check source diagnostics, retry the refresh, or add reference articles before generating a preview.",
            }
        if raw_candidate_count > 0 and returned_count <= 0:
            return {
                "status": "insufficient_total",
                "reason_code": "filtered_out_by_quality_bar",
                "message": (
                    f"Fetched {raw_candidate_count} candidate(s), but none cleared the current quality bar for this account."
                ),
                "recommended_action": "Widen the lane, relax source selection, or add trusted reference articles before previewing.",
            }
        return {
            "status": "insufficient_total",
            "reason_code": "insufficient_total",
            "message": (
                f"Only {returned_count} recommendation(s) cleared the minimum quality bar for this account, "
                f"below the requested {requested_min_count}."
            ),
            "recommended_action": "Refresh recommendations, widen the lane, or add reference articles before generating a preview.",
        }

    async def _load_latest_diagnostics(
        self,
        *,
        account_id: str,
        db: AsyncSession,
        rows: list[RecommendedContentItemModel],
        filtered_view: bool,
    ) -> dict[str, Any]:
        snapshot = await account_analysis_service.get_latest_snapshot(account_id, db)
        if (
            not filtered_view
            and snapshot is not None
            and isinstance(snapshot.recommendation_diagnostics_json, dict)
        ):
            return snapshot.recommendation_diagnostics_json
        return self._build_diagnostics_payload(rows=rows, source_diagnostics=[])

    def _build_diagnostics_payload(
        self,
        *,
        rows: list[RecommendedContentItemModel],
        source_diagnostics: list[dict[str, Any]],
        promoted_high_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        ranked_rows = sorted(rows, key=self._recommendation_quality_score, reverse=True)
        dynamic_high_bar = self._dynamic_high_relevance_bar(ranked_rows)
        source_summary = self._hydrate_source_diagnostics(
            ranked_rows,
            source_diagnostics,
            dynamic_high_bar=dynamic_high_bar,
            promoted_high_ids=promoted_high_ids or set(),
        )
        filter_diagnostics = self._build_filter_diagnostics(
            ranked_rows,
            dynamic_high_bar=dynamic_high_bar,
            promoted_high_ids=promoted_high_ids or set(),
        )
        filter_diagnostics["sources_failed_or_disabled"] = len(
            [
                item
                for item in source_summary
                if str(item.get("status") or "") in {"failed", "disabled"}
            ]
        )
        return {
            "source_diagnostics": source_summary,
            "filter_diagnostics": filter_diagnostics,
        }

    def _hydrate_source_diagnostics(
        self,
        rows: list[RecommendedContentItemModel],
        source_diagnostics: list[dict[str, Any]],
        *,
        dynamic_high_bar: float | None = None,
        promoted_high_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        promoted_high_ids = promoted_high_ids or set()
        grouped: dict[str, dict[str, int]] = {}
        for row in rows:
            payload = row.source_payload_json if isinstance(row.source_payload_json, dict) else {}
            collector = payload.get("collector") if isinstance(payload.get("collector"), dict) else {}
            source_key = str(collector.get("source_key") or row.source_type or "external").strip()
            bucket = grouped.setdefault(
                source_key,
                {"candidate_count": 0, "high_relevance_count": 0, "extended_count": 0},
            )
            bucket["candidate_count"] += 1
            if row.id in promoted_high_ids or self._is_high_relevance(row, dynamic_high_bar=dynamic_high_bar):
                bucket["high_relevance_count"] += 1
            elif self._is_extended_candidate(row):
                bucket["extended_count"] += 1

        hydrated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in source_diagnostics:
            source_key = str(item.get("source_key") or "").strip() or "external"
            seen.add(source_key)
            counts = grouped.get(source_key, {})
            candidate_count = int(item.get("candidate_count") or 0)
            high_relevance_count = int(counts.get("high_relevance_count") or 0)
            extended_count = int(counts.get("extended_count") or 0)
            accepted_count = high_relevance_count + extended_count
            hydrated.append(
                {
                    **item,
                    "candidate_count": max(candidate_count, int(counts.get("candidate_count") or 0)),
                    "high_relevance_count": high_relevance_count,
                    "extended_count": extended_count,
                    "filtered_out_count": max(candidate_count - accepted_count, 0),
                }
            )

        for source_key, counts in grouped.items():
            if source_key in seen:
                continue
            accepted_count = int(counts.get("high_relevance_count") or 0) + int(counts.get("extended_count") or 0)
            hydrated.append(
                {
                    "source_key": source_key,
                    "label": source_key,
                    "source_type": "cached_only",
                    "status": "cached_only",
                    "query": None,
                    "candidate_count": int(counts.get("candidate_count") or 0),
                    "high_relevance_count": int(counts.get("high_relevance_count") or 0),
                    "extended_count": int(counts.get("extended_count") or 0),
                    "filtered_out_count": max(int(counts.get("candidate_count") or 0) - accepted_count, 0),
                    "error_code": None,
                    "error_message": None,
                    "detail": "Only cached recommendation rows were available for this source.",
                }
            )

        hydrated.sort(
            key=lambda item: (
                int(item.get("high_relevance_count") or 0),
                int(item.get("extended_count") or 0),
                int(item.get("candidate_count") or 0),
            ),
            reverse=True,
        )
        return hydrated

    def _build_filter_diagnostics(
        self,
        rows: list[RecommendedContentItemModel],
        *,
        dynamic_high_bar: float | None = None,
        promoted_high_ids: set[str] | None = None,
    ) -> dict[str, int]:
        promoted_high_ids = promoted_high_ids or set()
        diagnostics = {
            "raw_candidate_count": len(rows),
            "high_relevance_count": 0,
            "extended_count": 0,
            "filtered_out_count": 0,
            "filtered_low_relevance_count": 0,
            "filtered_low_authority_count": 0,
            "sources_with_candidates": 0,
            "sources_failed_or_disabled": 0,
        }
        source_keys: set[str] = set()
        for row in rows:
            payload = row.source_payload_json if isinstance(row.source_payload_json, dict) else {}
            collector = payload.get("collector") if isinstance(payload.get("collector"), dict) else {}
            source_key = str(collector.get("source_key") or row.source_type or "").strip()
            if source_key:
                source_keys.add(source_key)
            if row.id in promoted_high_ids or self._is_high_relevance(row, dynamic_high_bar=dynamic_high_bar):
                diagnostics["high_relevance_count"] += 1
                continue
            if self._is_extended_candidate(row):
                diagnostics["extended_count"] += 1
                continue
            diagnostics["filtered_out_count"] += 1
            if float(row.authority_score or 0.0) < 0.35:
                diagnostics["filtered_low_authority_count"] += 1
            else:
                diagnostics["filtered_low_relevance_count"] += 1
        diagnostics["sources_with_candidates"] = len(source_keys)
        return diagnostics


recommendation_service = RecommendationService()
