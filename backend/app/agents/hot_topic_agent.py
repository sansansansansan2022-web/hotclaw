"""Hot topic agent for account-aware source scouting."""

from __future__ import annotations

import json
from typing import Any

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.core.config import settings
from app.core.exceptions import ConfigError
from app.core.logger import get_logger
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service
from app.skills.registry import skill_registry
from app.skills.services.evidence_service import evidence_service
from app.skills.services.skill_router_service import skill_router_service
from app.skills.services.skill_runtime_service import skill_runtime_service

logger = get_logger(__name__)


class HotTopicAgent(BaseAgent):
    """Discover relevant hot topics while separating source scouting from writing."""

    agent_id = "hot_topic_agent"
    name = "Hot Topic Agent"
    description = "Scout candidate sources, then analyze hot topics that fit the account."

    input_schema = {
        "type": "object",
        "properties": {
            "profile": {"type": "object"},
            "account_context": {"type": "object"},
            "ops_context": {"type": "object"},
            "history_summary": {"type": "string"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
        "required": ["profile"],
    }

    output_schema = {
        "type": "object",
        "properties": {
            "hot_topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "source": {"type": "string"},
                        "heat_score": {"type": "integer"},
                        "summary": {"type": "string"},
                        "relevance_score": {"type": "number"},
                    },
                },
            },
            "query_plan": {"type": "object"},
            "source_candidates": {"type": "array"},
            "source_snippets": {"type": "array"},
            "reference_digest": {"type": "object"},
            "external_evidence": {"type": "object"},
            "fetched_evidence": {"type": "array"},
            "selected_evidence": {"type": "array"},
            "evidence_summaries": {"type": "object"},
            "citation_guardrails": {"type": "object"},
        },
    }

    supported_skills = [
        "hot_topic_fetch_skill",
        "github_project_curator_skill",
        "scholar_paper_search_skill",
    ]

    default_system_prompt = """You are a source-aware hot topic analyst for Chinese public-account writing.

Your job is to:
1. read the account profile and strategy hints,
2. review both scoped source-scout results and grounded external evidence,
3. return only the hot topics that are genuinely relevant to this account.

Return strict JSON only.

Rules:
- Keep the account positioning and lane front and center.
- Prefer topics that are both timely and writable for this audience.
- Do not write the article. Only rank and summarize source-backed topic opportunities.
- Ignore source candidates that are noisy, generic, or off-positioning.
- If external evidence is present, treat it as the citation source of truth.
"""

    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        profile = input_data.get("profile") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        system_prompt = self.get_system_prompt(context)

        try:
            query_plan = query_planner_service.build_plan(
                profile=profile,
                account_context=account_context,
                ops_context=ops_context,
            )
            logger.info("hot_topic_query_plan_ready", lane=query_plan.get("lane"))

            evidence_payload = await self._collect_external_evidence(
                profile=profile,
                account_context=account_context,
                query_plan=query_plan,
                context=context,
            )

            skill_result = await self._fetch_with_skill(query_plan)
            if skill_result.get("status") != "success":
                error = skill_result.get("error", {})
                raise RuntimeError(f"Skill failed: {error.get('message') or error.get('code') or 'unknown'}")

            search_results = skill_result.get("data", {}).get("results", [])
            evidence_results = self._evidence_to_search_results(
                evidence_payload.get("selected_evidence") or []
            )
            combined_results = self._merge_search_results(search_results, evidence_results)

            scout_package = reference_digest_service.build_source_scout_package(
                search_results=combined_results,
                query_plan=query_plan,
                account_context=account_context,
                ops_context=ops_context,
                limit=8,
            )
            merged_source_candidates = self._merge_source_candidates(
                scout_package.get("source_candidates", []),
                evidence_service.to_source_candidates(evidence_payload.get("selected_evidence") or []),
            )
            merged_source_snippets = self._merge_source_snippets(
                scout_package.get("source_snippets", []),
                evidence_payload.get("selected_evidence") or [],
            )
            merged_reference_digest = self._merge_reference_digest(
                scout_package.get("reference_digest", {}),
                evidence_payload.get("evidence_summaries", {}),
            )
            logger.info(
                "hot_topic_source_scout_complete",
                search_result_count=len(search_results),
                evidence_result_count=len(evidence_results),
                selected_evidence_count=len(evidence_payload.get("selected_evidence") or []),
            )

            if not combined_results:
                return self._success(
                    {
                        "hot_topics": [],
                        "query_plan": query_plan,
                        "source_candidates": merged_source_candidates,
                        "source_snippets": merged_source_snippets,
                        "reference_digest": merged_reference_digest,
                        **evidence_payload,
                    }
                )

            structured_topics = await self._analyze_with_llm(
                search_results=combined_results,
                profile=profile,
                account_context=account_context,
                system_prompt=system_prompt,
                query_plan=query_plan,
                reference_digest=merged_reference_digest,
                selected_evidence=evidence_payload.get("selected_evidence") or [],
                evidence_summaries=evidence_payload.get("evidence_summaries") or {},
            )

            return self._success(
                {
                    "hot_topics": structured_topics,
                    "query_plan": query_plan,
                    "source_candidates": merged_source_candidates,
                    "source_snippets": merged_source_snippets,
                    "reference_digest": merged_reference_digest,
                    **evidence_payload,
                }
            )
        except Exception as exc:
            logger.error("hot_topic_agent_error", error=str(exc))
            return self._failure(code="HOT_TOPIC_ERROR", message=str(exc))

    async def _collect_external_evidence(
        self,
        *,
        profile: dict[str, Any],
        account_context: dict[str, Any],
        query_plan: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        plans = skill_router_service.plan_invocations(
            profile=profile,
            task_goal=str(
                query_plan.get("selected_topic")
                or query_plan.get("selected_title")
                or profile.get("positioning_raw")
                or account_context.get("positioning")
                or ""
            ),
            current_node="hot_topic_analysis",
            workspace_context=context,
            account_context=account_context,
        )
        if not plans:
            return {
                "external_evidence": {
                    "fetched_evidence": [],
                    "selected_evidence": [],
                    "evidence_summaries": {},
                    "citation_guardrails": {
                        "must_ground_titles_in_evidence": False,
                        "must_ground_repo_names_in_evidence": False,
                    },
                },
                "fetched_evidence": [],
                "selected_evidence": [],
                "evidence_summaries": {},
                "citation_guardrails": {
                    "must_ground_titles_in_evidence": False,
                    "must_ground_repo_names_in_evidence": False,
                },
            }

        db = context.get("db")
        task_id = context.get("task_id")
        if not isinstance(db, AsyncSession):
            raise ConfigError("Skill runtime requires a database session in agent context.")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ConfigError("Skill runtime requires task_id in agent context.")

        merged = {
            "external_evidence": {
                "fetched_evidence": [],
                "selected_evidence": [],
                "evidence_summaries": {},
                "citation_guardrails": {
                    "must_ground_titles_in_evidence": True,
                    "must_ground_repo_names_in_evidence": True,
                },
            },
            "fetched_evidence": [],
            "selected_evidence": [],
            "evidence_summaries": {},
            "citation_guardrails": {
                "must_ground_titles_in_evidence": True,
                "must_ground_repo_names_in_evidence": True,
            },
        }
        fetched_seen_ids: set[str] = set()
        selected_seen_ids: set[str] = set()
        for plan in plans:
            invocation = await skill_runtime_service.invoke(
                skill_name=plan["skill_name"],
                input_data=plan["input_data"],
                db=db,
                task_id=task_id,
                workspace_id=task_id,
                account_id=context.get("account_id"),
            )
            workspace_payload = invocation.get("workspace_payload") or {}
            for item in workspace_payload.get("fetched_evidence") or []:
                evidence_id = str(item.get("id") or item.get("source_id") or "")
                if evidence_id and evidence_id in fetched_seen_ids:
                    continue
                if evidence_id:
                    fetched_seen_ids.add(evidence_id)
                merged["fetched_evidence"].append(item)
            for item in workspace_payload.get("selected_evidence") or []:
                evidence_id = str(item.get("id") or item.get("source_id") or "")
                if evidence_id and evidence_id in selected_seen_ids:
                    continue
                if evidence_id:
                    selected_seen_ids.add(evidence_id)
                merged["selected_evidence"].append(item)
            merged["evidence_summaries"].update(workspace_payload.get("evidence_summaries") or {})
            merged["citation_guardrails"].update(workspace_payload.get("citation_guardrails") or {})

        merged["external_evidence"] = {
            "fetched_evidence": merged["fetched_evidence"],
            "selected_evidence": merged["selected_evidence"],
            "evidence_summaries": merged["evidence_summaries"],
            "citation_guardrails": merged["citation_guardrails"],
        }
        return merged

    async def _fetch_with_skill(self, query_plan: dict[str, Any]) -> dict[str, Any]:
        try:
            skill = skill_registry.get("hot_topic_fetch_skill")
            queries = query_plan.get("primary_queries") or query_plan.get("secondary_queries") or []
            return await skill.execute(
                {
                    "queries": queries,
                    "keywords": query_plan.get("search_terms") or [],
                    "engines": ["weixin", "sogou", "360"],
                    "max_results_per_engine": 8,
                }
            )
        except Exception as exc:
            logger.warning("hot_topic_skill_fetch_failed", error=str(exc))
            return {
                "status": "failed",
                "skill_id": "hot_topic_fetch_skill",
                "data": None,
                "error": {"code": "SKILL_ERROR", "message": str(exc)},
            }

    async def _analyze_with_llm(
        self,
        *,
        search_results: list[dict[str, Any]],
        profile: dict[str, Any],
        account_context: dict[str, Any],
        system_prompt: str,
        query_plan: dict[str, Any],
        reference_digest: dict[str, Any],
        selected_evidence: list[dict[str, Any]],
        evidence_summaries: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not search_results:
            return []

        user_prompt = self._build_analysis_prompt(
            search_results=search_results,
            profile=profile,
            account_context=account_context,
            query_plan=query_plan,
            reference_digest=reference_digest,
            selected_evidence=selected_evidence,
            evidence_summaries=evidence_summaries,
        )

        try:
            model = settings.llm_model_name
            if not model.startswith("dashscope/"):
                model = f"dashscope/{model}"

            response = await litellm.acompletion(
                model=model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base_url,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=settings.llm_timeout,
                custom_llm_provider="dashscope",
            )
            content = response.choices[0].message.content
            data = self._parse_json(content)
            topics = data.get("hot_topics")
            return topics if isinstance(topics, list) else self._fallback_topics(search_results)
        except json.JSONDecodeError:
            logger.warning("hot_topic_llm_json_parse_error")
            return self._fallback_topics(search_results)
        except Exception as exc:
            logger.warning("hot_topic_llm_analysis_error", error=str(exc))
            return self._fallback_topics(search_results)

    def _build_analysis_prompt(
        self,
        *,
        search_results: list[dict[str, Any]],
        profile: dict[str, Any],
        account_context: dict[str, Any],
        query_plan: dict[str, Any],
        reference_digest: dict[str, Any],
        selected_evidence: list[dict[str, Any]],
        evidence_summaries: dict[str, str],
    ) -> str:
        account_snapshot = {
            "account_name": account_context.get("account_name") or "unknown",
            "positioning": account_context.get("positioning") or profile.get("positioning_raw") or "",
            "audience": account_context.get("audience") or profile.get("target_audience") or "",
            "tone_style": account_context.get("tone_style") or profile.get("tone") or "",
            "content_strategy": account_context.get("content_strategy") or "",
        }
        search_snapshot = [
            {
                "title": item.get("title"),
                "source": item.get("source"),
                "source_type": item.get("source_type"),
                "snippet": item.get("snippet"),
            }
            for item in search_results[:16]
            if isinstance(item, dict)
        ]
        evidence_snapshot = [
            {
                "title": item.get("title"),
                "source_type": item.get("source_type"),
                "summary": item.get("summary"),
                "selected_reason": item.get("selected_reason"),
                "risk_flags": item.get("risk_flags"),
            }
            for item in selected_evidence[:10]
            if isinstance(item, dict)
        ]

        return "\n".join(
            [
                "Review the source-scout results and pick the hot topics worth carrying into planning.",
                "",
                "ACCOUNT SNAPSHOT",
                json.dumps(account_snapshot, ensure_ascii=False, indent=2),
                "",
                "QUERY PLAN",
                json.dumps(query_plan, ensure_ascii=False, indent=2),
                "",
                "REFERENCE DIGEST",
                json.dumps(reference_digest, ensure_ascii=False, indent=2),
                "",
                "EVIDENCE SUMMARIES",
                json.dumps(evidence_summaries, ensure_ascii=False, indent=2),
                "",
                "SELECTED EXTERNAL EVIDENCE",
                json.dumps(evidence_snapshot, ensure_ascii=False, indent=2),
                "",
                "SOURCE SCOUT RESULTS",
                json.dumps(search_snapshot, ensure_ascii=False, indent=2),
                "",
                "RETURN CONTRACT",
                "- Return JSON with hot_topics only.",
                "- Include 5-8 items when possible.",
                "- Each hot topic must include title, source, heat_score, summary, relevance_score.",
                "- relevance_score must reflect the account, not just general popularity.",
                "- Prefer topics that can be grounded in the external evidence list when evidence exists.",
                "- Skip topics below 0.5 relevance.",
            ]
        )

    def _fallback_topics(self, search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fallback: list[dict[str, Any]] = []
        for item in search_results[:8]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            fallback.append(
                {
                    "title": title,
                    "source": str(item.get("source") or item.get("source_type") or "source").strip(),
                    "heat_score": 70,
                    "summary": str(item.get("snippet") or title)[:120],
                    "relevance_score": 0.62,
                }
            )
        return fallback

    def _evidence_to_search_results(self, selected_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in selected_evidence:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            source_type = str(item.get("source_type") or "external_evidence").strip() or "external_evidence"
            results.append(
                {
                    "title": title,
                    "source": source_type,
                    "source_type": source_type,
                    "url": item.get("url"),
                    "snippet": str(item.get("summary") or item.get("selected_reason") or title).strip(),
                    "source_id": item.get("source_id"),
                }
            )
        return results

    def _merge_search_results(
        self,
        search_results: list[dict[str, Any]],
        evidence_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*evidence_results, *search_results]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            normalized = "".join(ch.lower() for ch in title if ch.isalnum())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(item)
        return merged

    def _merge_source_candidates(
        self,
        scout_candidates: list[dict[str, Any]],
        evidence_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*evidence_candidates, *scout_candidates]:
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("source_id") or item.get("source_title") or item.get("title") or "").strip()
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            merged.append(item)
        return merged[:12]

    def _merge_source_snippets(
        self,
        scout_snippets: list[dict[str, Any]],
        selected_evidence: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        snippets = list(scout_snippets or [])
        for item in selected_evidence[:6]:
            if not isinstance(item, dict):
                continue
            snippets.append(
                {
                    "source_id": item.get("source_id") or item.get("id"),
                    "source_title": item.get("title"),
                    "source_type": item.get("source_type"),
                    "snippet": item.get("summary") or item.get("selected_reason"),
                }
            )
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in snippets:
            if not isinstance(item, dict):
                continue
            source_id = str(item.get("source_id") or item.get("source_title") or "").strip()
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            deduped.append(item)
        return deduped[:12]

    def _merge_reference_digest(
        self,
        reference_digest: dict[str, Any],
        evidence_summaries: dict[str, str],
    ) -> dict[str, Any]:
        if not isinstance(reference_digest, dict):
            reference_digest = {}
        merged = dict(reference_digest)
        if evidence_summaries:
            merged["external_evidence_summary"] = evidence_summaries
            useful_points = merged.get("useful_points")
            normalized_useful_points = useful_points if isinstance(useful_points, list) else []
            normalized_useful_points.extend(list(evidence_summaries.values()))
            merged["useful_points"] = normalized_useful_points[:8]
        return merged

    def _parse_json(self, content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        return json.loads(text)

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        profile = input_data.get("profile") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        query_plan = query_planner_service.build_plan(
            profile=profile,
            account_context=account_context,
            ops_context=ops_context,
        )
        skill_plans = skill_router_service.plan_invocations(
            profile=profile,
            task_goal=str(
                query_plan.get("selected_topic")
                or query_plan.get("selected_title")
                or profile.get("positioning_raw")
                or account_context.get("positioning")
                or ""
            ),
            current_node="hot_topic_analysis",
            workspace_context={},
            account_context=account_context,
        )
        if skill_plans:
            return None

        reference_digest = reference_digest_service.build_reference_digest(
            account_context=account_context,
            ops_context=ops_context,
            query_plan=query_plan,
            limit=3,
        )
        return self._success(
            {
                "hot_topics": [],
                "query_plan": query_plan,
                "source_candidates": [],
                "source_snippets": [],
                "reference_digest": reference_digest,
                "external_evidence": {
                    "fetched_evidence": [],
                    "selected_evidence": [],
                    "evidence_summaries": {},
                    "citation_guardrails": {
                        "must_ground_titles_in_evidence": False,
                        "must_ground_repo_names_in_evidence": False,
                    },
                },
                "fetched_evidence": [],
                "selected_evidence": [],
                "evidence_summaries": {},
                "citation_guardrails": {
                    "must_ground_titles_in_evidence": False,
                    "must_ground_repo_names_in_evidence": False,
                },
            }
        )
