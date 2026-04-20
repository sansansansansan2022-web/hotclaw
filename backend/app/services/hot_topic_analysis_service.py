"""Hot topic analysis orchestration extracted from the agent shell."""

from __future__ import annotations

import asyncio
import json
from time import monotonic
from typing import TYPE_CHECKING, Any

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConfigError
from app.core.logger import get_logger
from app.services.query_planner_service import query_planner_service
from app.services.reference_digest_service import reference_digest_service
from app.skills.registry import skill_registry
from app.skills.services.evidence_service import evidence_service
from app.skills.services.skill_router_service import skill_router_service
from app.skills.services.skill_runtime_service import skill_runtime_service

if TYPE_CHECKING:
    from app.agents.base import AgentResult, BaseAgent

logger = get_logger(__name__)


class HotTopicAnalysisService:
    """Cross-layer hot topic orchestration kept outside the agent shell."""

    async def execute(
        self,
        *,
        agent: BaseAgent,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        profile = input_data.get("profile") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        system_prompt = agent.get_system_prompt(context)
        started_at = monotonic()
        node_timeout_seconds = self._node_timeout_seconds(context)

        try:
            query_plan = input_data.get("query_plan") if isinstance(input_data.get("query_plan"), dict) else None
            if not isinstance(query_plan, dict):
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
                started_at=started_at,
                node_timeout_seconds=node_timeout_seconds,
            )
            evidence_payload = self._merge_explicit_evidence_payload(evidence_payload, input_data)

            explicit_search_results = self._source_candidates_to_search_results(input_data.get("source_candidates") or [])
            if explicit_search_results:
                search_results = explicit_search_results
            else:
                skill_result = await self._fetch_with_skill(query_plan)
                if skill_result.get("status") != "success":
                    error = skill_result.get("error", {})
                    raise RuntimeError(f"Skill failed: {error.get('message') or error.get('code') or 'unknown'}")
                search_results = (
                    skill_result.get("data", {}).get("results")
                    or skill_result.get("data", {}).get("topics")
                    or []
                )

            evidence_results = self._evidence_to_search_results(evidence_payload.get("selected_evidence") or [])
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
                input_data.get("reference_digest")
                if isinstance(input_data.get("reference_digest"), dict)
                else scout_package.get("reference_digest", {}),
                evidence_payload.get("evidence_summaries", {}),
            )
            logger.info(
                "hot_topic_source_scout_complete",
                search_result_count=len(search_results),
                evidence_result_count=len(evidence_results),
                selected_evidence_count=len(evidence_payload.get("selected_evidence") or []),
            )

            if not combined_results:
                return agent._attach_runtime_trace(
                    agent._success(
                        {
                            "hot_topics": [],
                            "query_plan": query_plan,
                            "source_candidates": merged_source_candidates,
                            "source_snippets": merged_source_snippets,
                            "reference_digest": merged_reference_digest,
                            **evidence_payload,
                        }
                    ),
                    context,
                )

            remaining_budget = self._remaining_budget_seconds(
                started_at,
                node_timeout_seconds=node_timeout_seconds,
            )
            if remaining_budget <= self._minimum_llm_budget_seconds():
                logger.warning(
                    "hot_topic_llm_skipped_low_budget",
                    remaining_seconds=round(remaining_budget, 2),
                )
                structured_topics = self._fallback_topics(combined_results)
            else:
                structured_topics = await self._analyze_with_llm(
                    agent=agent,
                    search_results=combined_results,
                    profile=profile,
                    account_context=account_context,
                    context=context,
                    system_prompt=system_prompt,
                    query_plan=query_plan,
                    reference_digest=merged_reference_digest,
                    selected_evidence=evidence_payload.get("selected_evidence") or [],
                    evidence_summaries=evidence_payload.get("evidence_summaries") or {},
                    timeout_seconds=self._llm_timeout_for_remaining_budget(remaining_budget),
                )

            return agent._attach_runtime_trace(
                agent._success(
                    {
                        "hot_topics": structured_topics,
                        "query_plan": query_plan,
                        "source_candidates": merged_source_candidates,
                        "source_snippets": merged_source_snippets,
                        "reference_digest": merged_reference_digest,
                        **evidence_payload,
                    }
                ),
                context,
            )
        except Exception as exc:
            logger.error("hot_topic_agent_error", error=str(exc))
            return agent._attach_runtime_trace(
                agent._failure(code="HOT_TOPIC_ERROR", message=str(exc)),
                context,
            )

    async def fallback(
        self,
        *,
        agent: BaseAgent,
        error: Exception,
        input_data: dict[str, Any],
    ) -> AgentResult | None:
        profile = input_data.get("profile") or {}
        account_context = input_data.get("account_context") or {}
        ops_context = input_data.get("ops_context") or {}
        query_plan = input_data.get("query_plan") if isinstance(input_data.get("query_plan"), dict) else None
        if not isinstance(query_plan, dict):
            query_plan = query_planner_service.build_plan(
                profile=profile,
                account_context=account_context,
                ops_context=ops_context,
            )

        evidence_payload = self._merge_explicit_evidence_payload(
            self._empty_evidence_payload(),
            input_data,
        )
        explicit_search_results = self._source_candidates_to_search_results(input_data.get("source_candidates") or [])
        evidence_results = self._evidence_to_search_results(evidence_payload.get("selected_evidence") or [])
        combined_results = self._merge_search_results(explicit_search_results, evidence_results)

        if combined_results:
            scout_package = reference_digest_service.build_source_scout_package(
                search_results=combined_results,
                query_plan=query_plan,
                account_context=account_context,
                ops_context=ops_context,
                limit=8,
            )
            hot_topics = self._fallback_topics(combined_results)
            source_candidates = self._merge_source_candidates(
                scout_package.get("source_candidates", []),
                evidence_service.to_source_candidates(evidence_payload.get("selected_evidence") or []),
            )
            source_snippets = self._merge_source_snippets(
                scout_package.get("source_snippets", []),
                evidence_payload.get("selected_evidence") or [],
            )
            base_reference_digest = scout_package.get("reference_digest", {})
        else:
            hot_topics = self._fallback_topics_from_positioning(
                query_plan=query_plan,
                profile=profile,
                account_context=account_context,
            )
            source_candidates = evidence_service.to_source_candidates(evidence_payload.get("selected_evidence") or [])
            source_snippets = self._merge_source_snippets(
                [],
                evidence_payload.get("selected_evidence") or [],
            )
            base_reference_digest = reference_digest_service.build_reference_digest(
                account_context=account_context,
                ops_context=ops_context,
                query_plan=query_plan,
                source_candidates=source_candidates,
                limit=3,
            )
            base_reference_digest["summary"] = (
                "Hot topic fallback relied on account positioning because real-time source scouting timed out."
            )

        explicit_reference_digest = (
            input_data.get("reference_digest") if isinstance(input_data.get("reference_digest"), dict) else {}
        )
        reference_digest = self._merge_reference_digest(
            {**base_reference_digest, **explicit_reference_digest},
            evidence_payload.get("evidence_summaries", {}),
        )

        logger.warning(
            "hot_topic_agent_fallback_used",
            error=str(error),
            source_candidate_count=len(source_candidates),
            selected_evidence_count=len(evidence_payload.get("selected_evidence") or []),
            hot_topic_count=len(hot_topics),
        )
        return agent._success(
            {
                "hot_topics": hot_topics,
                "query_plan": query_plan,
                "source_candidates": source_candidates,
                "source_snippets": source_snippets,
                "reference_digest": reference_digest,
                **evidence_payload,
            }
        )

    async def _collect_external_evidence(
        self,
        *,
        profile: dict[str, Any],
        account_context: dict[str, Any],
        query_plan: dict[str, Any],
        context: dict[str, Any],
        started_at: float,
        node_timeout_seconds: int,
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
            return self._empty_evidence_payload()

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
            remaining_budget = self._remaining_budget_seconds(
                started_at,
                node_timeout_seconds=node_timeout_seconds,
                reserve_seconds=self._minimum_llm_budget_seconds() + self._execution_safety_buffer_seconds(),
            )
            if remaining_budget <= self._minimum_optional_skill_budget_seconds():
                logger.warning(
                    "hot_topic_external_skill_budget_exhausted",
                    task_id=task_id,
                    skill_name=plan["skill_name"],
                    remaining_seconds=round(remaining_budget, 2),
                )
                break
            try:
                invocation = await asyncio.wait_for(
                    skill_runtime_service.invoke(
                        skill_name=plan["skill_name"],
                        input_data=plan["input_data"],
                        db=db,
                        task_id=task_id,
                        workspace_id=task_id,
                        account_id=context.get("account_id"),
                    ),
                    timeout=min(
                        self._max_external_skill_budget_seconds(),
                        max(1.0, remaining_budget),
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "hot_topic_external_skill_skipped",
                    task_id=task_id,
                    skill_name=plan["skill_name"],
                    error=str(exc),
                )
                continue
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

        if not merged["selected_evidence"] and not merged["fetched_evidence"]:
            merged["citation_guardrails"] = {
                "must_ground_titles_in_evidence": False,
                "must_ground_repo_names_in_evidence": False,
            }

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
        agent: BaseAgent,
        search_results: list[dict[str, Any]],
        profile: dict[str, Any],
        account_context: dict[str, Any],
        context: dict[str, Any],
        system_prompt: str,
        query_plan: dict[str, Any],
        reference_digest: dict[str, Any],
        selected_evidence: list[dict[str, Any]],
        evidence_summaries: dict[str, Any],
        timeout_seconds: int,
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
            response = await agent.run_litellm_completion(
                context=context,
                completion_callable=litellm.acompletion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=timeout_seconds,
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
        evidence_summaries: dict[str, Any],
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

    def _remaining_budget_seconds(
        self,
        started_at: float,
        *,
        node_timeout_seconds: int,
        reserve_seconds: float = 0.0,
    ) -> float:
        return max(
            float(node_timeout_seconds) - (monotonic() - started_at) - reserve_seconds,
            0.0,
        )

    def _node_timeout_seconds(self, context: dict[str, Any]) -> int:
        configured = context.get("node_timeout_seconds")
        if isinstance(configured, (int, float)) and configured > 0:
            return int(configured)
        return int(settings.agent_timeout)

    def _minimum_llm_budget_seconds(self) -> int:
        return max(min(settings.llm_timeout, 30), 15)

    def _minimum_optional_skill_budget_seconds(self) -> int:
        return 8

    def _max_external_skill_budget_seconds(self) -> int:
        return min(max(settings.scholar_skill_timeout_seconds, 10), 25)

    def _execution_safety_buffer_seconds(self) -> int:
        return 5

    def _llm_timeout_for_remaining_budget(self, remaining_budget: float) -> int:
        effective = min(
            int(max(remaining_budget - self._execution_safety_buffer_seconds(), 5)),
            settings.llm_timeout,
        )
        return max(effective, 5)

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

    def _source_candidates_to_search_results(self, source_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in source_candidates:
            if not isinstance(item, dict):
                continue
            title = str(item.get("source_title") or item.get("title") or "").strip()
            if not title:
                continue
            source_type = str(item.get("source_type") or "selected_recommendation").strip() or "selected_recommendation"
            results.append(
                {
                    "title": title,
                    "source": str(item.get("source_name") or source_type).strip(),
                    "source_type": source_type,
                    "url": item.get("url"),
                    "snippet": str(item.get("snippet") or item.get("why_selected") or title).strip(),
                    "source_id": item.get("source_id"),
                }
            )
        return results

    def _merge_explicit_evidence_payload(
        self,
        merged_payload: dict[str, Any],
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(merged_payload or {})
        explicit_selected = (
            input_data.get("selected_evidence") if isinstance(input_data.get("selected_evidence"), list) else []
        )
        explicit_fetched = (
            input_data.get("fetched_evidence") if isinstance(input_data.get("fetched_evidence"), list) else []
        )
        explicit_summaries = (
            input_data.get("evidence_summaries") if isinstance(input_data.get("evidence_summaries"), dict) else {}
        )
        explicit_guardrails = (
            input_data.get("citation_guardrails") if isinstance(input_data.get("citation_guardrails"), dict) else {}
        )

        payload["fetched_evidence"] = self._merge_evidence_lists(
            explicit_fetched,
            payload.get("fetched_evidence") or [],
        )
        payload["selected_evidence"] = self._merge_evidence_lists(
            explicit_selected,
            payload.get("selected_evidence") or [],
        )
        payload["evidence_summaries"] = {**explicit_summaries, **(payload.get("evidence_summaries") or {})}
        payload["citation_guardrails"] = {**(payload.get("citation_guardrails") or {}), **explicit_guardrails}
        payload["external_evidence"] = {
            "fetched_evidence": payload["fetched_evidence"],
            "selected_evidence": payload["selected_evidence"],
            "evidence_summaries": payload["evidence_summaries"],
            "citation_guardrails": payload["citation_guardrails"],
        }
        return payload

    def _merge_evidence_lists(
        self,
        primary: list[dict[str, Any]],
        secondary: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*primary, *secondary]:
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("id") or item.get("source_id") or item.get("title") or "").strip()
            if not evidence_id or evidence_id in seen:
                continue
            seen.add(evidence_id)
            merged.append(item)
        return merged

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

    def _empty_evidence_payload(self) -> dict[str, Any]:
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

    def _fallback_topics_from_positioning(
        self,
        *,
        query_plan: dict[str, Any],
        profile: dict[str, Any],
        account_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        lane = query_plan.get("lane") if isinstance(query_plan.get("lane"), dict) else {}
        lane_label = str(lane.get("label") or lane.get("id") or "账号定位").strip()
        selected_title = str(query_plan.get("selected_title") or "").strip()
        selected_topic = str(query_plan.get("selected_topic") or "").strip()
        positioning = str(account_context.get("positioning") or profile.get("positioning_raw") or "").strip()
        audience = str(account_context.get("audience") or "").strip()

        account_keywords: list[str] = []
        for item in query_plan.get("account_keywords") or []:
            keyword = str(item or "").strip()
            if keyword and keyword not in account_keywords:
                account_keywords.append(keyword)

        candidates: list[tuple[str, str]] = []
        if selected_title:
            candidates.append(
                (
                    selected_title,
                    "Fallback kept the selected title direction because upstream source scouting timed out.",
                )
            )
        if selected_topic and selected_topic != selected_title:
            candidates.append(
                (
                    selected_topic,
                    "Fallback kept the selected topic direction so downstream planning can continue.",
                )
            )
        if lane_label:
            candidates.append(
                (
                    f"{lane_label} 赛道里今天最值得写的判断",
                    f"Fallback used the lane hint '{lane_label}' when real-time topic scouting timed out.",
                )
            )
        if account_keywords:
            keyword_label = " / ".join(account_keywords[:2])
            candidates.append(
                (
                    f"{keyword_label} 的工程落地观察",
                    "Fallback used account-fit keywords to preserve relevance after timeout.",
                )
            )
        if positioning:
            short_positioning = positioning[:28]
            candidates.append(
                (
                    f"{short_positioning}：从账号定位出发的今日选题",
                    "Fallback used the account positioning as the primary source of truth after timeout.",
                )
            )
        if not candidates:
            candidates.append(
                (
                    "结合账号定位整理本周最值得写的 AI 观察",
                    "Fallback generated a generic account-fit topic because no source candidates were available.",
                )
            )

        fallback_topics: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for index, (title, summary) in enumerate(candidates):
            normalized = "".join(ch.lower() for ch in title if ch.isalnum())
            if not normalized or normalized in seen_titles:
                continue
            seen_titles.add(normalized)
            fallback_topics.append(
                {
                    "title": title,
                    "source": "account_positioning_fallback",
                    "heat_score": max(56, 66 - index * 3),
                    "summary": summary[:160],
                    "relevance_score": round(max(0.56, 0.68 - index * 0.03), 3),
                }
            )
            if len(fallback_topics) >= 4:
                break

        if audience and fallback_topics:
            fallback_topics[0]["summary"] = (
                f"{fallback_topics[0]['summary']} Target reader: {audience[:48]}."
            )[:160]

        return fallback_topics

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


hot_topic_analysis_service = HotTopicAnalysisService()
