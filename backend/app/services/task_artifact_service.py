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
        "artifact_key": "outline_preview",
        "stage": "outline",
        "title": "Outline Preview",
        "source_node_ids": ("outline_planner",),
    },
    {
        "artifact_key": "section_drafts",
        "stage": "writing",
        "title": "Section Drafts",
        "source_node_ids": ("section_writer", "content_writer_fallback"),
    },
    {
        "artifact_key": "assembled_article",
        "stage": "writing",
        "title": "Assembled Article",
        "source_node_ids": ("article_assembler", "article_assembly", "content_writer_fallback"),
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
        "artifact_key": "audit_summary",
        "stage": "audit",
        "title": "Audit Summary",
        "source_node_ids": ("audit",),
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
        node_map = {row.node_id: row for row in (task.node_runs or [])}
        return [
            self._build_artifact(task=task, result_data=result_data, node_map=node_map, spec=spec)
            for spec in ARTIFACT_SPECS
        ]

    def _build_artifact(
        self,
        *,
        task: TaskModel,
        result_data: dict[str, Any],
        node_map: dict[str, TaskNodeRunModel],
        spec: dict[str, Any],
    ) -> dict[str, Any]:
        artifact_key = str(spec["artifact_key"])
        source_node_ids = list(spec["source_node_ids"])
        source_nodes = [node_map[node_id] for node_id in source_node_ids if node_id in node_map]
        display_payload = self._display_payload_for(artifact_key, result_data, source_nodes)
        raw_output = self._raw_output_for(artifact_key, result_data, source_nodes)
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
    ) -> dict[str, Any] | None:
        if artifact_key == "profile_snapshot":
            payload = {
                "profile": result_data.get("profile"),
                "style_profile": result_data.get("style_profile"),
                "content_pipeline": result_data.get("content_pipeline"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "evidence_bundle":
            payload = {
                "query_plan": result_data.get("query_plan"),
                "source_candidates": result_data.get("source_candidates"),
                "reference_digest": result_data.get("reference_digest"),
                "selected_evidence": result_data.get("selected_evidence"),
                "external_evidence": result_data.get("external_evidence"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "topic_selection":
            payload = {
                "hot_topics": result_data.get("hot_topics"),
                "topics": result_data.get("topics"),
                "selected_topic": self._selected_topic(result_data),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "title_candidates":
            payload = {
                "titles": result_data.get("titles"),
                "selected_title": self._selected_title(result_data),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "outline_preview":
            outline_plan = result_data.get("outline_plan") or result_data.get("outline_seed")
            if outline_plan is None:
                return None
            return {"outline_plan": outline_plan}
        if artifact_key == "section_drafts":
            section_drafts = result_data.get("section_drafts")
            if section_drafts is None:
                return None
            return {"section_drafts": section_drafts}
        if artifact_key == "assembled_article":
            payload = {
                "content": result_data.get("content"),
                "content_pipeline": result_data.get("content_pipeline"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "review_summary":
            payload = {
                "review_results": result_data.get("review_results"),
                "style_review": result_data.get("style_review"),
                "structure_review": result_data.get("structure_review"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        if artifact_key == "rewrite_summary":
            rewrite_result = result_data.get("rewrite_result")
            return {"rewrite_result": rewrite_result} if rewrite_result is not None else None
        if artifact_key == "audit_summary":
            payload = {
                "audit_result": result_data.get("audit_result"),
                "evaluation": result_data.get("evaluation"),
            }
            return payload if any(value is not None for value in payload.values()) else None
        return None

    def _raw_output_for(
        self,
        artifact_key: str,
        result_data: dict[str, Any],
        source_nodes: list[TaskNodeRunModel],
    ) -> dict[str, Any] | None:
        node_outputs = {
            node.node_id: node.output_data
            for node in source_nodes
            if isinstance(node.output_data, dict)
        }
        payload = self._display_payload_for(artifact_key, result_data, source_nodes)
        if payload is None and not node_outputs:
            return None
        return {
            "result_slice": payload,
            "node_outputs": node_outputs,
        }

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
        query_plan = result_data.get("query_plan")
        if isinstance(query_plan, dict):
            return query_plan.get("selected_topic")
        return None

    def _selected_title(self, result_data: dict[str, Any]) -> Any:
        titles = result_data.get("titles")
        if isinstance(titles, dict) and titles.get("selected_title") is not None:
            return titles.get("selected_title")
        content = result_data.get("content")
        if isinstance(content, dict):
            return content.get("selected_title")
        query_plan = result_data.get("query_plan")
        if isinstance(query_plan, dict):
            return query_plan.get("selected_title")
        return None


task_artifact_service = TaskArtifactService()
