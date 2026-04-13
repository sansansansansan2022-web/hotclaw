"""Build explicit compose previews before formal task execution."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.models.tables import ComposeSelectionSessionModel, RecommendedContentItemModel, ReferenceSourceModel
from app.services.account_analysis_service import account_analysis_service
from app.services.account_service import account_service
from app.services.compose_selection_service import compose_selection_service
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service

logger = get_logger(__name__)


class ComposePreviewService:
    """Turn selected recommendations into an explicit preview and runtime payload."""

    async def build_preview_bundle(
        self,
        *,
        account_id: str,
        selection_session_id: str,
        db: AsyncSession,
        creation_note: str | None = None,
        preferred_lane: str | None = None,
        title_direction: str | None = None,
        preview_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = await compose_selection_service.update_session_preferences(
            account_id,
            selection_session_id,
            db,
            creation_note=creation_note,
            preferred_lane=preferred_lane,
            title_direction=title_direction,
            status="previewed",
        )
        snapshot = await account_analysis_service.get_or_refresh_snapshot(account_id, db)
        account_context = await account_service.get_account_context(account_id, db) or {}
        selected_recommendations = await compose_selection_service.list_selected_recommendations(account_id, session, db)
        selected_reference_sources = await compose_selection_service.list_selected_reference_sources(account_id, session, db)

        query_plan = self._build_query_plan(
            snapshot=snapshot,
            account_context=account_context,
            session=session,
            recommendations=selected_recommendations,
            preview_payload=preview_payload,
        )
        topic_directions = self._build_topic_directions(
            recommendations=selected_recommendations,
            preferred_lane=session.preferred_lane,
            preview_payload=preview_payload,
        )
        title_directions = self._build_title_directions(
            topic_directions=topic_directions,
            session=session,
            preview_payload=preview_payload,
        )
        source_candidates = self._build_source_candidates(selected_recommendations)
        reference_digest = reference_digest_service.build_reference_digest(
            account_context=account_context,
            ops_context={
                "run_strategy": {
                    "preferred_content_lane": session.preferred_lane,
                    "preferred_reference_source_ids": [
                        str(item) for item in (session.selected_reference_source_ids_json or [])
                    ],
                }
            },
            query_plan=query_plan,
            source_candidates=source_candidates,
            selected_topic=topic_directions[0]["title"] if topic_directions else query_plan.get("selected_topic"),
            selected_title=title_directions[0]["title"] if title_directions else None,
        )
        outline_preview = self._build_outline_preview(
            snapshot=snapshot,
            session=session,
            query_plan=query_plan,
            topic_directions=topic_directions,
            title_directions=title_directions,
            reference_digest=reference_digest,
            selected_recommendations=selected_recommendations,
            preview_payload=preview_payload,
        )

        visible_payload = {
            "selection_session": compose_selection_service.serialize_session(session),
            "account_profile_summary": {
                "positioning_summary": snapshot.positioning_summary,
                "audience_summary": snapshot.audience_summary,
                "tone_summary": snapshot.tone_summary,
                "preferred_lane": session.preferred_lane or ((query_plan.get("lane") or {}).get("label")),
                "style_keywords": snapshot.style_keywords_json or [],
                "creation_note": session.creation_note,
            },
            "source_bundle": self._build_source_bundle(selected_recommendations, selected_reference_sources),
            "selected_sources": self._serialize_selected_sources(selected_recommendations),
            "selected_reference_sources": self._serialize_selected_reference_sources(selected_reference_sources),
            "query_plan": self._build_query_plan_response(query_plan),
            "topic_directions": topic_directions,
            "title_directions": title_directions,
            "outline_preview": self._build_outline_preview_response(outline_preview),
            "citation_guardrails": self._build_citation_guardrails(),
        }
        runtime_payload = self._build_runtime_payload(
            session=session,
            selected_recommendations=selected_recommendations,
            selected_reference_sources=selected_reference_sources,
            query_plan=query_plan,
            reference_digest=reference_digest,
            outline_preview=outline_preview,
            visible_payload=visible_payload,
        )
        logger.info(
            "compose_preview_built",
            account_id=account_id,
            selection_session_id=session.id,
            selected_recommendation_count=len(selected_recommendations),
            selected_reference_source_count=len(selected_reference_sources),
        )
        return {
            "selection_session": session,
            "response": visible_payload,
            "runtime_payload": runtime_payload,
        }

    def _build_query_plan(
        self,
        *,
        snapshot,
        account_context: dict[str, Any],
        session: ComposeSelectionSessionModel,
        recommendations: list[RecommendedContentItemModel],
        preview_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(preview_payload, dict) and isinstance(preview_payload.get("query_plan"), dict):
            query_plan = dict(preview_payload.get("query_plan") or {})
            lane = query_plan.get("lane") if isinstance(query_plan.get("lane"), dict) else {}
            if session.preferred_lane and not lane.get("label"):
                query_plan["lane"] = {
                    "id": self._slugify(session.preferred_lane),
                    "label": session.preferred_lane,
                    "input_hint": session.preferred_lane,
                    "reason": "Selected during compose preview.",
                }
            return query_plan

        selected_topic = recommendations[0].title if recommendations else None
        return query_planner_service.build_plan(
            profile={
                "positioning_raw": snapshot.positioning_summary,
                "target_audience": snapshot.audience_summary or "",
                "tone": snapshot.tone_summary or "",
            },
            account_context=account_context,
            ops_context={
                "run_strategy": {
                    "preferred_content_lane": session.preferred_lane,
                }
            },
            selected_topic=selected_topic,
        )

    def _build_topic_directions(
        self,
        *,
        recommendations: list[RecommendedContentItemModel],
        preferred_lane: str | None,
        preview_payload: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if isinstance(preview_payload, dict) and isinstance(preview_payload.get("topic_directions"), list):
            normalized = [item for item in preview_payload.get("topic_directions") if isinstance(item, dict)]
            if normalized:
                return normalized

        directions: list[dict[str, Any]] = []
        for row in recommendations[:3]:
            directions.append(
                {
                    "title": row.title,
                    "angle": preferred_lane or self._angle_from_tags(row.topic_tags_json or []),
                    "topic_kind": self._infer_topic_kind(row),
                    "reason": row.reason or row.summary or "Selected for creation based on account fit and source quality.",
                    "source_ids": [row.id],
                }
            )
        return directions

    def _build_title_directions(
        self,
        *,
        topic_directions: list[dict[str, Any]],
        session: ComposeSelectionSessionModel,
        preview_payload: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if isinstance(preview_payload, dict) and isinstance(preview_payload.get("title_directions"), list):
            normalized = [item for item in preview_payload.get("title_directions") if isinstance(item, dict)]
            if normalized:
                return normalized

        directions: list[dict[str, Any]] = []
        style = session.title_direction or "清晰判断"
        for item in topic_directions[:3]:
            seed = str(item.get("title") or "").strip()
            if not seed:
                continue
            directions.append(
                {
                    "title": self._render_title(seed, style, item.get("topic_kind")),
                    "style": style,
                    "rationale": f"Anchor the piece on real evidence from {seed} while keeping the tone {style}.",
                }
            )
        return directions

    def _build_outline_preview(
        self,
        *,
        snapshot,
        session: ComposeSelectionSessionModel,
        query_plan: dict[str, Any],
        topic_directions: list[dict[str, Any]],
        title_directions: list[dict[str, Any]],
        reference_digest: dict[str, Any],
        selected_recommendations: list[RecommendedContentItemModel],
        preview_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if isinstance(preview_payload, dict) and isinstance(preview_payload.get("outline_preview"), dict):
            outline = dict(preview_payload.get("outline_preview") or {})
            if outline.get("sections"):
                return outline

        selected_topic = topic_directions[0]["title"] if topic_directions else (query_plan.get("selected_topic") or "Selected topic")
        selected_title = title_directions[0]["title"] if title_directions else selected_topic
        evidence_refs = [row.title for row in selected_recommendations[:3]]
        preferred_names = reference_digest.get("preferred_source_names") or []
        lane = session.preferred_lane or ((query_plan.get("lane") or {}).get("label")) or "内容洞察"

        sections = [
            {
                "section_id": "s1",
                "heading": "为什么这条线索现在值得写",
                "purpose": "快速交代读者当下为什么要关心这次选题。",
                "key_points": [
                    f"从 {selected_topic} 切入，而不是从泛背景开始。",
                    "点出账号受众真正关心的判断或机会。",
                ],
                "evidence_refs": evidence_refs[:1],
            },
            {
                "section_id": "s2",
                "heading": "核心事实与证据底座",
                "purpose": "把已选推荐和参考源整理成可写作的事实底座。",
                "key_points": [
                    "拆出最值得保留的 2-3 条事实线索。",
                    "区分什么是确定信息，什么是需要谨慎表述的推断。",
                ],
                "evidence_refs": evidence_refs[:2] or preferred_names[:2],
            },
            {
                "section_id": "s3",
                "heading": "账号自己的判断与角度",
                "purpose": "把事实转成账号可以拥有的观点，而不是复述新闻。",
                "key_points": [
                    f"沿着 {lane} 这条内容 lane 给出判断。",
                    "强调对目标读者最相关的价值、风险或边界。",
                ],
                "evidence_refs": evidence_refs[:2],
            },
            {
                "section_id": "s4",
                "heading": "读者可带走的结论",
                "purpose": "形成一个值得传播的结尾，不做空泛总结。",
                "key_points": [
                    "给出一条可执行的观察、判断或行动建议。",
                    "结尾和标题方向保持一致。",
                ],
                "evidence_refs": evidence_refs[:1],
            },
        ]
        return {
            "article_goal": f"围绕 {selected_topic} 为账号受众形成一篇可直接进入创作的内容方案。",
            "why_this_topic": "它同时满足账号定位、近期性和证据可得性。",
            "strategic_angle": session.preferred_lane or lane,
            "reference_basis": ", ".join(preferred_names[:2]) if preferred_names else "selected recommendations",
            "target_reader": snapshot.audience_summary or "账号核心读者",
            "content_lane": lane,
            "target_reader_takeaway": "读者应能获得更清晰的判断，而不是只看完一条资讯摘要。",
            "opening_hook": f"从 {selected_topic} 带来的最新变化或矛盾切入。",
            "emotional_arc": "发现 -> 理解 -> 判断 -> 落点",
            "sections": sections,
            "ending_cta": "用一句明确判断或建议收尾。",
            "estimated_word_count": 1400,
            "summary": f"{selected_title} 的创作预览已准备完成。",
        }

    def _build_runtime_payload(
        self,
        *,
        session: ComposeSelectionSessionModel,
        selected_recommendations: list[RecommendedContentItemModel],
        selected_reference_sources: list[ReferenceSourceModel],
        query_plan: dict[str, Any],
        reference_digest: dict[str, Any],
        outline_preview: dict[str, Any],
        visible_payload: dict[str, Any],
    ) -> dict[str, Any]:
        selected_evidence = self._build_selected_evidence(selected_recommendations)
        source_candidates = self._build_source_candidates(selected_recommendations)
        evidence_summaries = {
            "selected_recommendations": f"Selected {len(selected_recommendations)} recommendation(s) for this run.",
        }
        if selected_reference_sources:
            evidence_summaries["selected_reference_sources"] = (
                f"Linked {len(selected_reference_sources)} account reference source(s) into this run."
            )
        return {
            "selection_session_id": session.id,
            "selected_recommendations": self._serialize_selected_sources(selected_recommendations),
            "selected_reference_sources": self._serialize_selected_reference_sources(selected_reference_sources),
            "compose_preview": visible_payload,
            "query_plan": query_plan,
            "source_candidates": source_candidates,
            "source_snippets": [
                {
                    "source_id": item["source_id"],
                    "source_title": item["source_title"],
                    "source_type": item["source_type"],
                    "snippet": item["snippet"],
                }
                for item in source_candidates[:6]
            ],
            "reference_digest": reference_digest,
            "outline_seed": outline_preview,
            "creation_note": session.creation_note,
            "external_evidence": {
                "fetched_evidence": selected_evidence,
                "selected_evidence": selected_evidence,
                "evidence_summaries": evidence_summaries,
                "citation_guardrails": self._build_citation_guardrails(),
            },
            "fetched_evidence": selected_evidence,
            "selected_evidence": selected_evidence,
            "evidence_summaries": evidence_summaries,
            "citation_guardrails": self._build_citation_guardrails(),
        }

    def serialize_selected_sources(self, rows: list[RecommendedContentItemModel]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for row in rows:
            payloads.append(
                {
                    "id": row.id,
                    "title": row.title,
                    "summary": row.summary,
                    "source_type": row.source_type,
                    "source_name": row.source_name,
                    "source_url": row.source_url,
                    "reason": row.reason,
                    "topic_tags": row.topic_tags_json or [],
                }
            )
        return payloads

    def serialize_selected_reference_sources(self, rows: list[ReferenceSourceModel]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for row in rows:
            metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            payloads.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "source_type": row.source_type,
                    "sync_status": row.sync_status,
                    "notes": row.notes,
                    "preview": metadata.get("preview"),
                }
            )
        return payloads

    def _serialize_selected_sources(self, rows: list[RecommendedContentItemModel]) -> list[dict[str, Any]]:
        return self.serialize_selected_sources(rows)

    def _serialize_selected_reference_sources(self, rows: list[ReferenceSourceModel]) -> list[dict[str, Any]]:
        return self.serialize_selected_reference_sources(rows)

    def _build_source_candidates(self, rows: list[RecommendedContentItemModel]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for row in rows:
            candidates.append(
                {
                    "source_id": row.id,
                    "source_type": row.source_type,
                    "source_name": row.source_name or row.source_type,
                    "source_title": row.title,
                    "url": row.source_url,
                    "snippet": row.summary or row.reason or row.title,
                    "fit_score": round(
                        (
                            float(row.relevance_score or 0.0)
                            + float(row.authority_score or 0.0)
                            + float(row.freshness_score or 0.0)
                        )
                        / 3,
                        4,
                    ),
                    "origin": "selected_recommendation",
                    "why_selected": row.reason or "",
                }
            )
        return candidates

    def _build_source_bundle(
        self,
        selected_recommendations: list[RecommendedContentItemModel],
        selected_reference_sources: list[ReferenceSourceModel],
    ) -> dict[str, Any]:
        source_types = sorted(
            {
                str(row.source_type).strip()
                for row in selected_recommendations
                if str(row.source_type).strip()
            }
        )
        return {
            "selected_source_count": len(selected_recommendations),
            "selected_reference_source_count": len(selected_reference_sources),
            "source_types": source_types,
        }

    def _build_query_plan_response(self, query_plan: dict[str, Any]) -> dict[str, Any]:
        lane = query_plan.get("lane") if isinstance(query_plan.get("lane"), dict) else {}
        return {
            "lane": {
                "id": str(lane.get("id") or "general_insight"),
                "label": str(lane.get("label") or "General insight"),
                "input_hint": lane.get("input_hint"),
                "reason": str(lane.get("reason") or "Derived from account context and selected inputs."),
            },
            "selected_topic": query_plan.get("selected_topic"),
            "selected_title": query_plan.get("selected_title"),
            "primary_queries": list(query_plan.get("primary_queries") or []),
            "secondary_queries": list(query_plan.get("secondary_queries") or []),
            "source_preferences": list(query_plan.get("source_preferences") or []),
            "banned_angles": list(query_plan.get("banned_angles") or []),
            "search_terms": list(query_plan.get("search_terms") or []),
        }

    def _build_outline_preview_response(self, outline_preview: dict[str, Any]) -> dict[str, Any]:
        sections = outline_preview.get("sections") if isinstance(outline_preview.get("sections"), list) else []
        normalized_sections = []
        for item in sections:
            if not isinstance(item, dict):
                continue
            normalized_sections.append(
                {
                    "section_id": str(item.get("section_id") or item.get("id") or ""),
                    "heading": str(item.get("heading") or ""),
                    "purpose": str(item.get("purpose") or ""),
                    "key_points": list(item.get("key_points") or []),
                    "evidence_refs": list(item.get("evidence_refs") or []),
                }
            )
        return {
            "article_goal": str(outline_preview.get("article_goal") or ""),
            "why_this_topic": str(outline_preview.get("why_this_topic") or ""),
            "strategic_angle": str(outline_preview.get("strategic_angle") or ""),
            "reference_basis": str(outline_preview.get("reference_basis") or ""),
            "target_reader": str(outline_preview.get("target_reader") or ""),
            "content_lane": str(outline_preview.get("content_lane") or ""),
            "target_reader_takeaway": str(outline_preview.get("target_reader_takeaway") or ""),
            "opening_hook": str(outline_preview.get("opening_hook") or ""),
            "emotional_arc": str(outline_preview.get("emotional_arc") or ""),
            "sections": normalized_sections,
            "ending_cta": str(outline_preview.get("ending_cta") or ""),
            "estimated_word_count": int(outline_preview.get("estimated_word_count") or 1200),
            "summary": str(outline_preview.get("summary") or ""),
        }

    def _build_citation_guardrails(self) -> dict[str, bool]:
        return {
            "must_ground_titles_in_evidence": True,
            "must_ground_repo_names_in_evidence": True,
        }

    def _build_selected_evidence(self, rows: list[RecommendedContentItemModel]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for row in rows:
            evidence.append(
                {
                    "id": row.id,
                    "source_id": row.id,
                    "source_type": row.source_type,
                    "title": row.title,
                    "url": row.source_url,
                    "summary": row.summary,
                    "skill_name": "compose_selection",
                    "relevance_score": row.relevance_score,
                    "authority_score": row.authority_score,
                    "freshness_score": row.freshness_score,
                    "practical_score": row.relevance_score,
                    "selected_reason": row.reason,
                    "risk_flags": [],
                }
            )
        return evidence

    def _infer_topic_kind(self, row: RecommendedContentItemModel) -> str:
        if row.source_type == "scholar_paper":
            return "paper_digest"
        if row.source_type == "github_repo":
            return "github_project_review"
        tags = [str(item).lower() for item in (row.topic_tags_json or [])]
        if any("benchmark" in item for item in tags):
            return "benchmark_analysis"
        if any("tool" in item or "framework" in item for item in tags):
            return "tools_roundup"
        return "research_trend"

    def _angle_from_tags(self, tags: list[Any]) -> str:
        normalized = [str(item).strip() for item in tags if str(item).strip()]
        if normalized:
            return normalized[0]
        return "内容洞察"

    def _render_title(self, seed: str, style: str, topic_kind: Any) -> str:
        normalized_style = str(style or "").strip()
        if "拆解" in normalized_style:
            return f"{seed} 值不值得写一篇拆解？"
        if "方法" in normalized_style or str(topic_kind) == "industry_method_explainer":
            return f"{seed} 背后真正值得写的方法论是什么？"
        if str(topic_kind) == "github_project_review":
            return f"这个 GitHub 项目为什么值得认真看一眼：{seed}"
        if str(topic_kind) == "paper_digest":
            return f"这篇论文为什么值得读：{seed}"
        return f"{seed}，对这类账号来说真正值得写的角度是什么？"

    def _slugify(self, value: str) -> str:
        pieces = Counter(ch.lower() for ch in value if ch.isalnum())
        if not pieces:
            return "lane"
        return "".join(pieces.keys())[:32]


compose_preview_service = ComposePreviewService()
