"""Build task-scoped artifacts and effective input snapshots for task detail views."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import TaskModel, TaskNodeRunModel
from app.services.task_service import task_service


ARTIFACT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "artifact_key": "profile_snapshot",
        "stage": "profile",
        "title": "Profile Snapshot",
        "source_node_ids": ("profile_parsing",),
    },
    {
        "artifact_key": "evidence_bundle",
        "stage": "research",
        "title": "Evidence Bundle",
        "source_node_ids": ("hot_topic_analysis",),
    },
    {
        "artifact_key": "query_plan",
        "stage": "research",
        "title": "Query Plan",
        "source_node_ids": ("hot_topic_analysis",),
    },
    {
        "artifact_key": "reference_digest",
        "stage": "research",
        "title": "Reference Digest",
        "source_node_ids": ("hot_topic_analysis",),
    },
    {
        "artifact_key": "topic_selection",
        "stage": "planning",
        "title": "Topic Selection",
        "source_node_ids": ("hot_topic_analysis", "topic_planning"),
    },
    {
        "artifact_key": "title_candidates",
        "stage": "planning",
        "title": "Title Candidates",
        "source_node_ids": ("title_generation",),
    },
    {
        "artifact_key": "topic_package",
        "stage": "planning",
        "title": "Topic Package",
        "source_node_ids": ("hot_topic_analysis", "topic_planning", "title_generation"),
    },
    {
        "artifact_key": "outline_preview",
        "stage": "outline",
        "title": "Outline Preview",
        "source_node_ids": ("outline_planner",),
    },
    {
        "artifact_key": "outline_plan",
        "stage": "outline",
        "title": "Outline Plan",
        "source_node_ids": ("outline_planner",),
    },
    {
        "artifact_key": "section_drafts",
        "stage": "writing",
        "title": "Section Drafts",
        "source_node_ids": ("section_writer", "content_writing_fallback", "content_writer_fallback"),
    },
    {
        "artifact_key": "assembled_article",
        "stage": "writing",
        "title": "Assembled Article",
        "source_node_ids": ("article_assembler", "article_assembly", "content_writing_fallback", "content_writer_fallback"),
    },
    {
        "artifact_key": "review_summary",
        "stage": "review",
        "title": "Review Summary",
        "source_node_ids": ("style_reviewer", "structure_reviewer"),
    },
    {
        "artifact_key": "rewrite_summary",
        "stage": "rewrite",
        "title": "Rewrite Summary",
        "source_node_ids": ("rewrite_agent",),
    },
    {
        "artifact_key": "review_bundle",
        "stage": "review",
        "title": "Review Bundle",
        "source_node_ids": ("style_reviewer", "structure_reviewer", "rewrite_agent"),
    },
    {
        "artifact_key": "audit_summary",
        "stage": "audit",
        "title": "Audit Summary",
        "source_node_ids": ("audit",),
    },
    {
        "artifact_key": "draft_quality_gate",
        "stage": "gate",
        "title": "Draft Quality Gate",
        "source_node_ids": ("draft_quality_gate",),
    },
    {
        "artifact_key": "draft_gate_result",
        "stage": "gate",
        "title": "Draft Gate Result",
        "source_node_ids": ("audit", "draft_quality_gate"),
    },
    {
        "artifact_key": "post_process_result",
        "stage": "post_process",
        "title": "Post-process Result",
        "source_node_ids": ("post_process_agent",),
    },
)


class TaskArtifactService:
    """Create stable, user-facing task artifacts from task and node outputs."""

    _explicit_input_keys: tuple[str, ...] = (
        "selection_session_id",
        "selected_recommendations",
        "selected_reference_sources",
        "compose_preview",
        "query_plan",
        "source_candidates",
        "source_snippets",
        "reference_digest",
        "outline_seed",
        "creation_note",
        "external_evidence",
        "fetched_evidence",
        "selected_evidence",
        "evidence_summaries",
        "citation_guardrails",
    )

    async def list_task_artifacts(self, task_id: str, db: AsyncSession) -> list[dict[str, Any]]:
        task = await task_service.get_task_with_nodes(task_id, db)
        return self._build_artifacts(task)

    async def get_task_artifact(
        self,
        task_id: str,
        artifact_key: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        task = await task_service.get_task_with_nodes(task_id, db)
        artifacts = {item["artifact_key"]: item for item in self._build_artifacts(task)}
        artifact = artifacts.get(artifact_key)
        if artifact is None:
            raise ValueError(f"unsupported artifact key: {artifact_key}")
        return artifact

    async def get_effective_input(self, task_id: str, db: AsyncSession) -> dict[str, Any]:
        task = await task_service.get_task(task_id, db)
        input_data = task.input_data if isinstance(task.input_data, dict) else {}
        explicit_input = {
            key: input_data.get(key)
            for key in self._explicit_input_keys
            if input_data.get(key) is not None
        }
        return {
            "task_id": task.id,
            "account_id": task.account_id,
            "workflow_id": task.workflow_id,
            "status": task.status,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "positioning": input_data.get("positioning"),
            "ops_context": input_data.get("ops_context"),
            "explicit_input": explicit_input,
            "selection_session_id": explicit_input.get("selection_session_id"),
            "selected_recommendations": explicit_input.get("selected_recommendations") or [],
            "selected_reference_sources": explicit_input.get("selected_reference_sources") or [],
            "compose_preview": explicit_input.get("compose_preview"),
            "query_plan": explicit_input.get("query_plan"),
            "reference_digest": explicit_input.get("reference_digest"),
            "outline_seed": explicit_input.get("outline_seed"),
            "creation_note": explicit_input.get("creation_note"),
            "external_evidence": explicit_input.get("external_evidence"),
            "input_data": input_data,
        }

    def _build_artifacts(self, task: TaskModel) -> list[dict[str, Any]]:
        result_data = task.result_data if isinstance(task.result_data, dict) else {}
        input_data = task.input_data if isinstance(task.input_data, dict) else {}
        node_map = {row.node_id: row for row in (task.node_runs or [])}
        return [
            self._build_artifact(task=task, result_data=result_data, input_data=input_data, node_map=node_map, spec=spec)
            for spec in ARTIFACT_SPECS
        ]

    def _build_artifact(
        self,
        *,
        task: TaskModel,
        result_data: dict[str, Any],
        input_data: dict[str, Any],
        node_map: dict[str, TaskNodeRunModel],
        spec: dict[str, Any],
    ) -> dict[str, Any]:
        artifact_key = str(spec["artifact_key"])
        source_node_ids = list(spec["source_node_ids"])
        source_nodes = [node_map[node_id] for node_id in source_node_ids if node_id in node_map]
        display_payload = self._display_payload_for(artifact_key, result_data, source_nodes, input_data)
        raw_output = self._raw_output_for(artifact_key, result_data, source_nodes, input_data)
        status = self._artifact_status(
            task_status=str(task.status),
            has_payload=display_payload is not None,
            source_nodes=source_nodes,
        )
        return {
            "artifact_key": artifact_key,
            "stage": spec["stage"],
            "title": spec["title"],
            "status": status,
            "display_payload": display_payload,
            "raw_output": raw_output,
            "source_node_ids": source_node_ids,
            "updated_at": self._latest_timestamp(source_nodes, fallback=task.updated_at),
        }

    def _display_payload_for(
        self,
        artifact_key: str,
        result_data: dict[str, Any],
        source_nodes: list[TaskNodeRunModel],
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        input_data = input_data or {}
        if artifact_key == "profile_snapshot":
            profile_output = self._node_output(source_nodes, "profile_parsing")
            payload = {
                "profile": self._coalesce(
                    result_data.get("profile"),
                    profile_output.get("profile"),
                    profile_output,
                ),
                "style_profile": self._coalesce(
                    result_data.get("style_profile"),
                    profile_output.get("style_profile"),
                ),
                "retrieved_memories": self._coalesce(
                    result_data.get("retrieved_memories"),
                    profile_output.get("retrieved_memories"),
                ),
                "content_pipeline": result_data.get("content_pipeline"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "evidence_bundle":
            hot_topic_output = self._node_output(source_nodes, "hot_topic_analysis")
            payload = {
                "query_plan": self._coalesce(result_data.get("query_plan"), hot_topic_output.get("query_plan"), input_data.get("query_plan")),
                "source_candidates": self._coalesce(result_data.get("source_candidates"), hot_topic_output.get("source_candidates")),
                "reference_digest": self._coalesce(
                    result_data.get("reference_digest"),
                    hot_topic_output.get("reference_digest"),
                    input_data.get("reference_digest"),
                ),
                "selected_evidence": self._coalesce(
                    result_data.get("selected_evidence"),
                    hot_topic_output.get("selected_evidence"),
                    input_data.get("selected_evidence"),
                ),
                "external_evidence": self._coalesce(
                    result_data.get("external_evidence"),
                    hot_topic_output.get("external_evidence"),
                    input_data.get("external_evidence"),
                ),
                "retrieved_memories": self._coalesce(result_data.get("retrieved_memories"), hot_topic_output.get("retrieved_memories")),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "query_plan":
            hot_topic_output = self._node_output(source_nodes, "hot_topic_analysis")
            query_plan = self._coalesce(
                result_data.get("query_plan"),
                hot_topic_output.get("query_plan"),
                input_data.get("query_plan"),
            )
            if query_plan is None:
                return None
            return {
                "contract_version": "v1",
                "query_plan": query_plan,
                "display_fields": ["lane", "selected_topic", "selected_title", "primary_queries", "banned_angles"],
                "fallback_source": None if result_data.get("query_plan") else "input_data",
                "handoff_metrics": {
                    "primary_query_count": len((query_plan or {}).get("primary_queries") or []) if isinstance(query_plan, dict) else 0,
                    "search_term_count": len((query_plan or {}).get("search_terms") or []) if isinstance(query_plan, dict) else 0,
                    "has_selected_topic": bool((query_plan or {}).get("selected_topic")) if isinstance(query_plan, dict) else False,
                    "has_selected_title": bool((query_plan or {}).get("selected_title")) if isinstance(query_plan, dict) else False,
                },
            }
        if artifact_key == "reference_digest":
            hot_topic_output = self._node_output(source_nodes, "hot_topic_analysis")
            reference_digest = self._coalesce(
                result_data.get("reference_digest"),
                hot_topic_output.get("reference_digest"),
                input_data.get("reference_digest"),
            )
            if reference_digest is None:
                return None
            return {
                "contract_version": "v1",
                "reference_digest": reference_digest,
                "display_fields": ["summary", "preferred_source_names", "style_takeaways", "useful_points"],
                "fallback_source": None if result_data.get("reference_digest") else "input_data",
                "handoff_metrics": {
                    "preferred_source_count": len((reference_digest or {}).get("preferred_source_names") or []) if isinstance(reference_digest, dict) else 0,
                    "useful_point_count": len((reference_digest or {}).get("useful_points") or []) if isinstance(reference_digest, dict) else 0,
                    "source_digest_count": len((reference_digest or {}).get("source_digests") or []) if isinstance(reference_digest, dict) else 0,
                },
            }
        if artifact_key == "topic_selection":
            hot_topic_output = self._node_output(source_nodes, "hot_topic_analysis")
            topic_output = self._node_output(source_nodes, "topic_planning")
            topic_payload = self._coalesce(result_data.get("topics"), topic_output)
            merged = {
                **result_data,
                "hot_topics": self._coalesce(result_data.get("hot_topics"), hot_topic_output.get("hot_topics"), hot_topic_output),
                "topics": topic_payload,
            }
            payload = {
                "hot_topics": merged.get("hot_topics"),
                "topics": self._list_from_payload(topic_payload, "topics") or topic_payload,
                "selected_topic": self._selected_topic(merged),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "title_candidates":
            title_output = self._node_output(source_nodes, "title_generation")
            title_payload = self._coalesce(result_data.get("titles"), title_output)
            merged = {
                **result_data,
                "titles": title_payload,
            }
            payload = {
                "titles": self._list_from_payload(title_payload, "titles") or title_payload,
                "selected_title": self._selected_title(merged),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "topic_package":
            hot_topic_output = self._node_output(source_nodes, "hot_topic_analysis")
            topic_output = self._node_output(source_nodes, "topic_planning")
            title_output = self._node_output(source_nodes, "title_generation")
            query_plan = self._coalesce(result_data.get("query_plan"), hot_topic_output.get("query_plan"), input_data.get("query_plan"))
            topic_payload = self._coalesce(result_data.get("topics"), topic_output)
            title_payload = self._coalesce(result_data.get("titles"), title_output)
            selected_topic = self._selected_topic({**result_data, "topics": topic_payload, "titles": title_payload, "query_plan": query_plan})
            selected_title = self._selected_title({**result_data, "titles": title_payload, "query_plan": query_plan})
            payload = {
                "contract_version": "v1",
                "hot_topics": self._coalesce(result_data.get("hot_topics"), hot_topic_output.get("hot_topics"), hot_topic_output),
                "topic_candidates": self._list_from_payload(topic_payload, "topics") or topic_payload,
                "title_candidates": self._list_from_payload(title_payload, "titles") or title_payload,
                "selected_topic": selected_topic,
                "selected_title": selected_title,
                "query_plan": query_plan,
                "display_fields": ["selected_topic", "selected_title", "topic_candidates", "title_candidates"],
                "fallback_source": None,
                "handoff_metrics": {
                    "hot_topic_count": len(((self._coalesce(result_data.get("hot_topics"), hot_topic_output.get("hot_topics"), hot_topic_output) or {}).get("hot_topics") or [])) if isinstance(self._coalesce(result_data.get("hot_topics"), hot_topic_output.get("hot_topics"), hot_topic_output), dict) else 0,
                    "topic_candidate_count": len(self._list_from_payload(topic_payload, "topics") or []) if topic_payload is not None else 0,
                    "title_candidate_count": len(self._list_from_payload(title_payload, "titles") or []) if title_payload is not None else 0,
                    "has_selected_topic": bool(selected_topic),
                    "has_selected_title": bool(selected_title),
                },
            }
            return payload if any(value is not None for key, value in payload.items() if key != "handoff_metrics") else None
        if artifact_key == "outline_preview":
            outline_output = self._node_output(source_nodes, "outline_planner")
            outline_plan = self._coalesce(
                result_data.get("outline_plan"),
                result_data.get("outline_seed"),
                outline_output.get("outline_plan"),
                outline_output,
                input_data.get("outline_seed"),
            )
            if outline_plan is None:
                return None
            return {"outline_plan": outline_plan}
        if artifact_key == "outline_plan":
            outline_output = self._node_output(source_nodes, "outline_planner")
            outline_plan = self._coalesce(
                result_data.get("outline_plan"),
                result_data.get("outline_seed"),
                outline_output.get("outline_plan"),
                outline_output,
                input_data.get("outline_seed"),
            )
            if outline_plan is None:
                return None
            sections = (outline_plan or {}).get("sections") if isinstance(outline_plan, dict) else None
            return {
                "contract_version": "v1",
                "outline_plan": outline_plan,
                "display_fields": ["summary", "opening_hook", "sections", "ending_cta"],
                "fallback_source": None if result_data.get("outline_plan") else "input_data",
                "handoff_metrics": {
                    "section_count": len(sections or []) if isinstance(sections, list) else 0,
                    "estimated_word_count": (outline_plan or {}).get("estimated_word_count") if isinstance(outline_plan, dict) else None,
                    "has_opening_hook": bool((outline_plan or {}).get("opening_hook")) if isinstance(outline_plan, dict) else False,
                },
            }
        if artifact_key == "section_drafts":
            section_output = self._node_output(source_nodes, "section_writer", "content_writing_fallback", "content_writer_fallback")
            section_drafts = self._coalesce(
                result_data.get("section_drafts"),
                section_output.get("section_drafts"),
                section_output if isinstance(section_output, list) else None,
            )
            if section_drafts is None:
                return None
            return {"section_drafts": section_drafts}
        if artifact_key == "assembled_article":
            article_output = self._node_output(source_nodes, "article_assembler", "article_assembly", "content_writing_fallback", "content_writer_fallback")
            payload = {
                "content": self._coalesce(result_data.get("content"), result_data.get("assembled_article"), article_output),
                "content_pipeline": result_data.get("content_pipeline"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "review_summary":
            style_output = self._node_output(source_nodes, "style_reviewer")
            structure_output = self._node_output(source_nodes, "structure_reviewer")
            review_results = result_data.get("review_results")
            if review_results is None:
                review_results = [
                    item
                    for item in (style_output, structure_output)
                    if item
                ]
            payload = {
                "review_results": review_results,
                "style_review": self._coalesce(result_data.get("style_review"), style_output),
                "structure_review": self._coalesce(result_data.get("structure_review"), structure_output),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "rewrite_summary":
            rewrite_result = self._coalesce(result_data.get("rewrite_result"), self._node_output(source_nodes, "rewrite_agent"))
            return {"rewrite_result": rewrite_result} if rewrite_result is not None else None
        if artifact_key == "review_bundle":
            style_output = self._coalesce(result_data.get("style_review"), self._node_output(source_nodes, "style_reviewer"))
            structure_output = self._coalesce(result_data.get("structure_review"), self._node_output(source_nodes, "structure_reviewer"))
            review_results = result_data.get("review_results")
            if review_results is None:
                review_results = [item for item in (style_output, structure_output) if item]
            rewrite_result = self._coalesce(result_data.get("rewrite_result"), self._node_output(source_nodes, "rewrite_agent"))
            issue_count = 0
            if isinstance(review_results, list):
                for item in review_results:
                    if isinstance(item, dict) and isinstance(item.get("issues"), list):
                        issue_count += len(item.get("issues") or [])
            payload = {
                "contract_version": "v1",
                "review_results": review_results,
                "style_review": style_output,
                "structure_review": structure_output,
                "rewrite_result": rewrite_result,
                "display_fields": ["review_results", "rewrite_result"],
                "fallback_source": None,
                "handoff_metrics": {
                    "reviewer_count": len(review_results or []) if isinstance(review_results, list) else 0,
                    "issue_count": issue_count,
                    "rewrite_used": bool((rewrite_result or {}).get("used_rewrite")) if isinstance(rewrite_result, dict) else False,
                },
            }
            return payload if any(value is not None for key, value in payload.items() if key != "handoff_metrics") else None
        if artifact_key == "audit_summary":
            audit_output = self._node_output(source_nodes, "audit")
            payload = {
                "audit_result": self._coalesce(result_data.get("audit_result"), audit_output),
                "evaluation": result_data.get("evaluation"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "draft_quality_gate":
            gate = self._coalesce(result_data.get("draft_quality_gate"), self._node_output(source_nodes, "draft_quality_gate"))
            return {"draft_quality_gate": gate} if gate is not None else None
        if artifact_key == "draft_gate_result":
            gate = self._coalesce(result_data.get("draft_quality_gate"), self._node_output(source_nodes, "draft_quality_gate"))
            audit_result = self._coalesce(result_data.get("audit_result"), self._node_output(source_nodes, "audit"))
            if gate is None and audit_result is None:
                return None
            issues = gate.get("issues") if isinstance(gate, dict) and isinstance(gate.get("issues"), list) else []
            failure_reasons = (
                gate.get("failure_reasons")
                if isinstance(gate, dict) and isinstance(gate.get("failure_reasons"), list)
                else []
            )
            return {
                "contract_version": "v1",
                "draft_quality_gate": gate,
                "audit_result": audit_result,
                "display_fields": ["draft_quality_gate", "audit_result"],
                "fallback_source": None,
                "handoff_metrics": {
                    "passed": bool(gate.get("passed")) if isinstance(gate, dict) else False,
                    "issue_count": len(issues),
                    "failure_reason_count": len(failure_reasons),
                },
            }
        if artifact_key == "post_process_result":
            post_process = self._coalesce(result_data.get("post_process_result"), self._node_output(source_nodes, "post_process_agent"))
            return {"post_process_result": post_process} if post_process is not None else None
        return None

    def _raw_output_for(
        self,
        artifact_key: str,
        result_data: dict[str, Any],
        source_nodes: list[TaskNodeRunModel],
        input_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        node_outputs = {
            node.node_id: node.output_data
            for node in source_nodes
            if isinstance(node.output_data, dict)
        }
        payload = self._display_payload_for(artifact_key, result_data, source_nodes, input_data)
        if payload is None and not node_outputs:
            return None
        return {
            "result_slice": payload,
            "node_outputs": node_outputs,
        }

    def _node_output(self, source_nodes: list[TaskNodeRunModel], *node_ids: str) -> dict[str, Any]:
        for node_id in node_ids:
            for node in source_nodes:
                if node.node_id == node_id and isinstance(node.output_data, dict):
                    return node.output_data
        return {}

    def _coalesce(self, *values: Any) -> Any:
        for value in values:
            if self._has_meaningful_value(value):
                return value
        return None

    def _has_meaningful_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (dict, list, tuple, set)):
            return bool(value)
        return True

    def _list_from_payload(self, value: Any, key: str) -> list[Any] | None:
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and isinstance(value.get(key), list):
            return value.get(key)
        return None

    def _artifact_status(
        self,
        *,
        task_status: str,
        has_payload: bool,
        source_nodes: list[TaskNodeRunModel],
    ) -> str:
        if has_payload:
            return "available"
        if any(node.status == "failed" for node in source_nodes):
            return "failed"
        if task_status in {"pending", "running"} or any(node.status in {"pending", "running"} for node in source_nodes):
            return "pending"
        return "missing"

    def _latest_timestamp(
        self,
        source_nodes: Iterable[TaskNodeRunModel],
        *,
        fallback: datetime | None,
    ) -> datetime | None:
        timestamps: list[datetime] = []
        for node in source_nodes:
            for value in (node.updated_at, node.completed_at, node.started_at, node.created_at):
                if isinstance(value, datetime):
                    timestamps.append(value)
                    break
        if timestamps:
            return max(timestamps)
        return fallback

    def _selected_topic(self, result_data: dict[str, Any]) -> Any:
        titles = result_data.get("titles")
        if isinstance(titles, dict) and titles.get("selected_topic") is not None:
            return titles.get("selected_topic")
        topics = result_data.get("topics")
        if isinstance(topics, dict):
            if topics.get("selected_topic") is not None:
                return topics.get("selected_topic")
            topic_items = topics.get("topics")
            if isinstance(topic_items, list):
                for item in topic_items:
                    if isinstance(item, dict) and item.get("title"):
                        return item.get("title")
        if isinstance(topics, list):
            for item in topics:
                if isinstance(item, dict) and item.get("title"):
                    return item.get("title")
        query_plan = result_data.get("query_plan")
        if isinstance(query_plan, dict):
            return query_plan.get("selected_topic")
        return None

    def _selected_title(self, result_data: dict[str, Any]) -> Any:
        titles = result_data.get("titles")
        if isinstance(titles, dict) and titles.get("selected_title") is not None:
            return titles.get("selected_title")
        if isinstance(titles, dict):
            title_items = titles.get("titles")
            if isinstance(title_items, list):
                for item in title_items:
                    if isinstance(item, dict):
                        candidate = item.get("text") or item.get("title")
                        if candidate:
                            return candidate
        if isinstance(titles, list):
            for item in titles:
                if isinstance(item, dict):
                    candidate = item.get("text") or item.get("title")
                    if candidate:
                        return candidate
        content = result_data.get("content")
        if isinstance(content, dict):
            return content.get("selected_title")
        query_plan = result_data.get("query_plan")
        if isinstance(query_plan, dict):
            return query_plan.get("selected_title")
        return None


task_artifact_service = TaskArtifactService()
