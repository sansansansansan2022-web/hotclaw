"""Workflow orchestrator with structured content pipeline support."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResult, BaseAgent
from app.agents.registry import agent_registry
from app.core.config import settings
from app.core.exceptions import AgentExecutionError, AgentTimeoutError
from app.core.logger import get_logger
from app.core.tracer import get_trace_id
from app.models.tables import AgentModel, TaskModel, TaskNodeRunModel
from app.orchestrator.broadcaster import broadcaster
from app.orchestrator.workspace import Workspace
from app.services.article_assembler_service import article_assembler_service

logger = get_logger(__name__)

STRUCTURED_CONTENT_NODE_IDS = {
    "content_drafting",
    "article_assembler",
}

TOPIC_SELECTION_NODE_IDS = {
    "topic_selection",
}

REVIEWER_NODE_IDS = {
    "editorial_review",
}

REWRITE_NODE_IDS = {
    "rewrite_agent",
}

LEGACY_CONTENT_FALLBACK_NODE = {
    "node_id": "content_writing_fallback",
    "agent_id": "content_writer_agent",
    "name": "Legacy Content Writer Fallback",
    "input_mapping": {
        "profile": "profile",
        "topics": "topics",
        "titles": "titles",
        "hot_topics": "hot_topics",
        "account_context": "account_context",
        "ops_context": "ops_context",
    },
    "output_key": "content",
    "required": True,
}

DEFAULT_WORKFLOW_NODES = [
    {
        "node_id": "context_building",
        "agent_id": "context_builder_agent",
        "name": "Context Building",
        "input_mapping": {
            "positioning": "input.positioning",
            "account_id": "input.account_id",
        },
        "output_key": "run_context",
        "required": True,
    },
    {
        "node_id": "hot_topic_analysis",
        "agent_id": "hot_topic_agent",
        "name": "Hot Topic Analysis",
        "input_mapping": {"profile": "profile"},
        "output_key": "hot_topics",
        "required": True,
    },
    {
        "node_id": "topic_selection",
        "agent_id": "topic_selection_agent",
        "name": "选题与标题",
        "input_mapping": {
            "profile": "profile",
            "hot_topics": "hot_topics",
            "account_context": "account_context",
            "ops_context": "ops_context",
        },
        "output_key": "topic_selection",
        "required": True,
    },
    {
        "node_id": "content_drafting",
        "agent_id": "content_drafter_agent",
        "name": "内容起草",
        "input_mapping": {
            "profile": "profile",
            "topics": "topics",
            "titles": "titles",
            "hot_topics": "hot_topics",
            "account_context": "account_context",
            "ops_context": "ops_context",
        },
        "output_key": "content_draft",
        "required": True,
    },
    {
        "node_id": "article_assembler",
        "agent_id": "article_assembler_service",
        "name": "Article Assembler",
        "executor": "service",
        "service": "article_assembler",
        "input_mapping": {
            "outline_plan": "outline_plan",
            "section_drafts": "section_drafts",
            "titles": "titles",
            "topics": "topics",
            "content": "content",
        },
        "output_key": "assembled_article",
        "required": True,
    },
    {
        "node_id": "editorial_review",
        "agent_id": "editorial_review_agent",
        "name": "编辑审核",
        "input_mapping": {
            "assembled_article": "assembled_article",
            "content": "content",
            "titles": "titles",
            "topics": "topics",
            "profile": "profile",
            "account_context": "account_context",
            "ops_context": "ops_context",
            "outline_plan": "outline_plan",
            "section_drafts": "section_drafts",
        },
        "output_key": "editorial_review",
        "required": False,
    },
    {
        "node_id": "rewrite_agent",
        "agent_id": "rewrite_agent",
        "name": "Rewrite Agent",
        "input_mapping": {
            "titles": "titles",
            "topics": "topics",
            "outline_plan": "outline_plan",
            "section_drafts": "section_drafts",
            "assembled_article": "assembled_article",
            "style_review": "style_review",
            "structure_review": "structure_review",
            "review_results": "review_results",
            "account_context": "account_context",
            "ops_context": "ops_context",
        },
        "output_key": "rewrite_result",
        "required": False,
    },
]


class OrchestratorEngine:
    """Run the content workflow sequentially and persist node-level traces."""

    def get_workflow_node_count(self) -> int:
        return len(DEFAULT_WORKFLOW_NODES)

    def get_node_display_name(self, node_id: str, agent_id: str | None = None) -> str:
        for node_def in [*DEFAULT_WORKFLOW_NODES, LEGACY_CONTENT_FALLBACK_NODE]:
            if node_def["node_id"] == node_id:
                return node_def["name"]
        return agent_id or node_id

    async def run(self, task: TaskModel, db: AsyncSession) -> dict[str, Any]:
        trace_id = get_trace_id()
        workspace = Workspace(task_id=task.id, input_data=task.input_data or {})
        total_tokens = 0
        structured_pipeline_degraded = False

        if task.account_id:
            if task.input_data is None:
                task.input_data = {}
            if isinstance(task.input_data, dict):
                task.input_data.setdefault("account_id", task.account_id)

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        db.add(task)
        await db.flush()

        for idx, node_def in enumerate(DEFAULT_WORKFLOW_NODES):
            node_id = node_def["node_id"]
            if structured_pipeline_degraded and node_id in STRUCTURED_CONTENT_NODE_IDS:
                await self._record_skipped_node(task.id, node_def, db, "legacy_content_fallback")
                continue

            node_run = TaskNodeRunModel(
                task_id=task.id,
                node_id=node_id,
                agent_id=node_def["agent_id"],
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(node_run)
            await db.flush()

            agent_input = workspace.extract_for_agent(node_def["input_mapping"])
            node_run.input_data = agent_input
            db.add(node_run)
            await db.flush()

            await broadcaster.broadcast(
                task.id,
                "node_start",
                {
                    "node_id": node_id,
                    "agent_id": node_def["agent_id"],
                    "name": node_def["name"],
                    "index": idx,
                    "total": len(DEFAULT_WORKFLOW_NODES),
                    "started_at": node_run.started_at.isoformat() if node_run.started_at else None,
                },
            )

            try:
                result = await self._execute_node(node_def, agent_input, workspace.snapshot(), trace_id, db)
                if result.is_success:
                    self._store_node_result(workspace, node_def, result.data or {})
                    node_run.status = "completed"
                    node_run.output_data = result.data
                else:
                    error_message = self._result_error_message(result)
                    if node_id in STRUCTURED_CONTENT_NODE_IDS:
                        await self._mark_node_failed(node_run, error_message, db)
                        await broadcaster.broadcast(
                            task.id,
                            "node_error",
                            {"node_id": node_id, "error": error_message},
                        )
                        await self._run_legacy_content_fallback(
                            task_id=task.id,
                            workspace=workspace,
                            db=db,
                            trace_id=trace_id,
                            reason=f"{node_id}: {error_message}",
                        )
                        structured_pipeline_degraded = True
                        continue

                    fallback_result = await self._execute_agent_fallback(
                        node_def["agent_id"],
                        AgentExecutionError(node_def["agent_id"], error_message),
                        agent_input,
                    )
                    if fallback_result and fallback_result.is_success:
                        self._store_node_result(workspace, node_def, fallback_result.data or {})
                        node_run.status = "completed"
                        node_run.output_data = fallback_result.data
                        node_run.degraded = True
                    elif node_def.get("required", True):
                        await self._mark_node_failed(node_run, error_message, db)
                        await broadcaster.broadcast(
                            task.id,
                            "node_error",
                            {"node_id": node_id, "error": error_message},
                        )
                        raise AgentExecutionError(node_def["agent_id"], error_message)
                    else:
                        node_run.status = "failed"
                        node_run.error_message = error_message
                        node_run.degraded = True
                        self._store_optional_node_failure(workspace, node_def, error_message)
                        await broadcaster.broadcast(
                            task.id,
                            "node_error",
                            {"node_id": node_id, "error": error_message},
                        )
            except asyncio.TimeoutError:
                error_message = f"agent {node_def['agent_id']} timed out"
                if node_id in STRUCTURED_CONTENT_NODE_IDS:
                    await self._mark_node_failed(node_run, error_message, db)
                    await broadcaster.broadcast(
                        task.id,
                        "node_error",
                        {"node_id": node_id, "error": error_message},
                    )
                    await self._run_legacy_content_fallback(
                        task_id=task.id,
                        workspace=workspace,
                        db=db,
                        trace_id=trace_id,
                        reason=f"{node_id}: timeout",
                    )
                    structured_pipeline_degraded = True
                    continue

                if node_def.get("required", True):
                    await self._mark_node_failed(node_run, error_message, db)
                    await broadcaster.broadcast(
                        task.id,
                        "node_error",
                        {"node_id": node_id, "error": error_message},
                    )
                    raise AgentTimeoutError(node_def["agent_id"])
                node_run.status = "failed"
                node_run.error_message = error_message
                node_run.degraded = True
                self._store_optional_node_failure(workspace, node_def, error_message)
                await broadcaster.broadcast(
                    task.id,
                    "node_error",
                    {"node_id": node_id, "error": error_message},
                )
            except AgentExecutionError:
                raise
            except Exception as exc:
                error_message = str(exc)
                if node_id in STRUCTURED_CONTENT_NODE_IDS:
                    await self._mark_node_failed(node_run, error_message, db)
                    await broadcaster.broadcast(
                        task.id,
                        "node_error",
                        {"node_id": node_id, "error": error_message},
                    )
                    await self._run_legacy_content_fallback(
                        task_id=task.id,
                        workspace=workspace,
                        db=db,
                        trace_id=trace_id,
                        reason=f"{node_id}: {error_message}",
                    )
                    structured_pipeline_degraded = True
                    continue

                logger.error(
                    "node_execution_error",
                    task_id=task.id,
                    node_id=node_id,
                    error=error_message,
                )
                if node_def.get("required", True):
                    await self._mark_node_failed(node_run, error_message, db)
                    await broadcaster.broadcast(
                        task.id,
                        "node_error",
                        {"node_id": node_id, "error": error_message},
                    )
                    raise AgentExecutionError(node_def["agent_id"], error_message)
                node_run.status = "failed"
                node_run.error_message = error_message
                node_run.degraded = True
                self._store_optional_node_failure(workspace, node_def, error_message)
                await broadcaster.broadcast(
                    task.id,
                    "node_error",
                    {"node_id": node_id, "error": error_message},
                )

            await self._finalize_node(node_run, db)
            if node_run.status == "completed":
                await broadcaster.broadcast(
                    task.id,
                    "node_complete",
                    {
                        "node_id": node_id,
                        "agent_id": node_def["agent_id"],
                        "name": node_def["name"],
                        "elapsed_seconds": node_run.elapsed_seconds,
                        "degraded": node_run.degraded,
                        "output_summary": self._summarize_output(node_run.output_data),
                    },
                )

            if node_run.prompt_tokens:
                total_tokens += node_run.prompt_tokens
            if node_run.completion_tokens:
                total_tokens += node_run.completion_tokens

        result_data = article_assembler_service.normalize_result_data(workspace.snapshot())
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        task.result_data = result_data
        task.total_tokens = total_tokens
        if task.started_at:
            task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds()
        db.add(task)
        await db.flush()

        await broadcaster.broadcast(
            task.id,
            "task_complete",
            {
                "task_id": task.id,
                "elapsed_seconds": task.elapsed_seconds,
            },
        )
        await broadcaster.close_task(task.id)
        return result_data

    async def _execute_node(
        self,
        node_def: dict[str, Any],
        input_data: dict[str, Any],
        context: dict[str, Any],
        trace_id: str,
        db: AsyncSession,
    ) -> AgentResult:
        if node_def.get("executor") == "service":
            return await self._execute_service_node(node_def, input_data)

        agent = agent_registry.get(node_def["agent_id"])
        effective_prompt = await self._resolve_system_prompt(
            node_def["agent_id"],
            agent.default_system_prompt,
            db,
        )
        enriched_context = dict(context)
        enriched_context["system_prompt"] = effective_prompt
        enriched_context["db"] = db
        return await self._execute_agent_with_timeout(agent, input_data, enriched_context, trace_id)

    async def _execute_service_node(
        self, node_def: dict[str, Any], input_data: dict[str, Any]
    ) -> AgentResult:
        if node_def.get("service") != "article_assembler":
            return AgentResult(
                status="failed",
                agent_name=node_def["agent_id"],
                error={"code": "UNKNOWN_SERVICE", "message": f"Unknown service node: {node_def.get('service')}"},
            )

        assembled = article_assembler_service.assemble_article(
            outline_plan=input_data.get("outline_plan"),
            section_drafts=input_data.get("section_drafts"),
            titles=input_data.get("titles"),
            topics=input_data.get("topics"),
            existing_content=input_data.get("content"),
        )
        return AgentResult(
            status="success",
            agent_name=node_def["agent_id"],
            data=assembled,
        )

    async def _execute_agent_with_timeout(
        self, agent: BaseAgent, input_data: dict, context: dict, trace_id: str
    ) -> AgentResult:
        return await asyncio.wait_for(
            agent.execute(input_data, context),
            timeout=settings.agent_timeout,
        )

    async def _execute_agent_fallback(
        self, agent_id: str, error: Exception, input_data: dict
    ) -> AgentResult | None:
        agent = agent_registry.get(agent_id)
        return await agent.fallback(error, input_data)

    async def _run_legacy_content_fallback(
        self,
        *,
        task_id: str,
        workspace: Workspace,
        db: AsyncSession,
        trace_id: str,
        reason: str,
    ) -> None:
        logger.warning(
            "structured_content_pipeline_fallback",
            task_id=task_id,
            reason=reason,
        )

        node_def = LEGACY_CONTENT_FALLBACK_NODE
        node_run = TaskNodeRunModel(
            task_id=task_id,
            node_id=node_def["node_id"],
            agent_id=node_def["agent_id"],
            status="running",
            started_at=datetime.now(timezone.utc),
            degraded=True,
        )
        db.add(node_run)
        await db.flush()

        agent_input = workspace.extract_for_agent(node_def["input_mapping"])
        node_run.input_data = agent_input
        db.add(node_run)
        await db.flush()

        await broadcaster.broadcast(
            task_id,
            "node_start",
            {
                "node_id": node_def["node_id"],
                "agent_id": node_def["agent_id"],
                "name": node_def["name"],
                "index": len(DEFAULT_WORKFLOW_NODES),
                "total": len(DEFAULT_WORKFLOW_NODES) + 1,
                "started_at": node_run.started_at.isoformat() if node_run.started_at else None,
            },
        )

        try:
            result = await self._execute_node(node_def, agent_input, workspace.snapshot(), trace_id, db)
            if not result.is_success:
                fallback_result = await self._execute_agent_fallback(
                    node_def["agent_id"],
                    AgentExecutionError(node_def["agent_id"], self._result_error_message(result)),
                    agent_input,
                )
                if not fallback_result or not fallback_result.is_success:
                    raise AgentExecutionError(
                        node_def["agent_id"],
                        self._result_error_message(result),
                    )
                result = fallback_result

            legacy_content = article_assembler_service.extract_article_payload(
                {
                    "content": result.data,
                    "titles": workspace.get("titles"),
                    "topics": workspace.get("topics"),
                }
            )
            workspace.set("content", legacy_content)
            workspace.set("assembled_article", legacy_content)
            workspace.set(
                "content_pipeline",
                {
                    "version": "phase6-structured-v1",
                    "used_structured_pipeline": False,
                    "fallback_to_content_writer": True,
                    "degraded": True,
                    "fallback_reason": reason,
                },
            )

            node_run.status = "completed"
            node_run.output_data = legacy_content
            node_run.degraded = True
            await self._finalize_node(node_run, db)
            await broadcaster.broadcast(
                task_id,
                "node_complete",
                {
                    "node_id": node_def["node_id"],
                    "agent_id": node_def["agent_id"],
                    "name": node_def["name"],
                    "elapsed_seconds": node_run.elapsed_seconds,
                    "degraded": True,
                    "output_summary": self._summarize_output(legacy_content),
                },
            )
        except Exception:
            await self._mark_node_failed(node_run, reason, db)
            await broadcaster.broadcast(
                task_id,
                "node_error",
                {"node_id": node_def["node_id"], "error": reason},
            )
            raise

    def _store_node_result(
        self, workspace: Workspace, node_def: dict[str, Any], data: dict[str, Any]
    ) -> None:
        node_id = node_def["node_id"]
        if node_id == "context_building":
            workspace.set(node_def["output_key"], data)
            profile = data.get("effective_profile")
            if isinstance(profile, dict):
                workspace.set("profile", profile)
                workspace.set("effective_profile", profile)
            if data.get("account_context") is not None:
                workspace.set("account_context", data.get("account_context"))
            oc = data.get("ops_context")
            if isinstance(oc, dict):
                workspace.set("ops_context", oc)
            if data.get("retrieved_memories") is not None:
                workspace.set("retrieved_memories", data.get("retrieved_memories"))
            return
        if node_id in TOPIC_SELECTION_NODE_IDS:
            # Expand topics and titles into separate workspace keys.
            workspace.set(node_def["output_key"], data)
            workspace.set("topics", {"topics": data.get("topics") or []})
            workspace.set("titles", {
                "selected_topic": data.get("selected_topic") or "",
                "titles": data.get("titles") or [],
            })
            return
        if node_id in STRUCTURED_CONTENT_NODE_IDS and node_id == "content_drafting":
            # Expand outline_plan and section_drafts into separate workspace keys.
            workspace.set(node_def["output_key"], data)
            if data.get("outline_plan") is not None:
                workspace.set("outline_plan", data["outline_plan"])
            if data.get("section_drafts") is not None:
                workspace.set("section_drafts", {"section_drafts": data["section_drafts"]})
            return
        if node_id == "article_assembler":
            workspace.set(node_def["output_key"], data)
            workspace.set("content", data)
            workspace.set(
                "content_pipeline",
                {
                    "version": "phase6-structured-v1",
                    "used_structured_pipeline": True,
                    "fallback_to_content_writer": False,
                    "degraded": False,
                },
            )
            return
        if node_id in REVIEWER_NODE_IDS:
            # editorial_review contains style + structure + audit sub-results.
            workspace.set(node_def["output_key"], data)
            style_result = self._normalize_review_result("style_reviewer", data.get("style") or {})
            structure_result = self._normalize_review_result("structure_reviewer", data.get("structure") or {})
            workspace.set("style_review", style_result)
            workspace.set("structure_review", structure_result)
            self._upsert_review_result(workspace, style_result)
            self._upsert_review_result(workspace, structure_result)
            audit_data = data.get("audit") or {}
            workspace.set("audit_result", audit_data)
            pipeline = workspace.get("content_pipeline")
            if not isinstance(pipeline, dict):
                pipeline = {}
            pipeline["review_attempted"] = True
            workspace.set("content_pipeline", pipeline)
            return
        if node_id in REWRITE_NODE_IDS:
            rewrite_result = self._normalize_rewrite_result(data)
            workspace.set(node_def["output_key"], rewrite_result)

            pipeline = workspace.get("content_pipeline")
            if not isinstance(pipeline, dict):
                pipeline = {}
            pipeline["rewrite_attempted"] = True
            pipeline["rewrite_used"] = bool(rewrite_result.get("used_rewrite"))
            pipeline["rewrite_failed"] = bool(rewrite_result.get("rewrite_failed"))
            if rewrite_result.get("used_rewrite"):
                assembled_article = article_assembler_service.extract_assembled_article_payload(
                    {
                        "assembled_article": workspace.get("assembled_article"),
                        "content": workspace.get("assembled_article") or workspace.get("content"),
                        "titles": workspace.get("titles"),
                        "topics": workspace.get("topics"),
                        "outline_plan": workspace.get("outline_plan"),
                        "section_drafts": workspace.get("section_drafts"),
                    }
                )
                revised_article = dict(assembled_article)
                revised_content = str(rewrite_result.get("revised_content_markdown") or "").strip()
                revised_article["content_markdown"] = revised_content
                revised_html = rewrite_result.get("revised_content_html")
                if revised_html:
                    revised_article["content_html"] = revised_html
                revised_article["word_count"] = article_assembler_service.count_words(revised_content)
                workspace.set("content", revised_article)
            workspace.set("content_pipeline", pipeline)
            return
        workspace.set(node_def["output_key"], data)

    def _store_optional_node_failure(
        self, workspace: Workspace, node_def: dict[str, Any], error_message: str
    ) -> None:
        node_id = node_def["node_id"]
        if node_id in REVIEWER_NODE_IDS:
            _degraded_review = {
                "passed": False,
                "score": None,
                "issues": [],
                "rewrite_suggestions": [],
                "failed": True,
                "degraded": True,
                "error_message": error_message,
            }
            style_degraded = {**_degraded_review, "reviewer": "style_reviewer", "summary": f"{node_def['name']} failed."}
            structure_degraded = {**_degraded_review, "reviewer": "structure_reviewer", "summary": f"{node_def['name']} failed."}
            audit_degraded = {
                "passed": False,
                "risk_level": "unknown",
                "issues": [],
                "overall_comment": f"{node_def['name']} failed. Manual review recommended.",
            }
            workspace.set(node_def["output_key"], {
                "editorial_passed": False,
                "style": style_degraded,
                "structure": structure_degraded,
                "audit": audit_degraded,
                "combined_rewrite_suggestions": [],
                "failed": True,
                "degraded": True,
                "error_message": error_message,
            })
            workspace.set("style_review", style_degraded)
            workspace.set("structure_review", structure_degraded)
            workspace.set("audit_result", audit_degraded)
            self._upsert_review_result(workspace, style_degraded)
            self._upsert_review_result(workspace, structure_degraded)
            pipeline = workspace.get("content_pipeline")
            if not isinstance(pipeline, dict):
                pipeline = {}
            pipeline["review_degraded"] = True
            pipeline["degraded"] = True
            workspace.set("content_pipeline", pipeline)
            return
        if node_id in REWRITE_NODE_IDS:
            rewrite_result = {
                "used_rewrite": False,
                "rewrite_failed": True,
                "rewrite_skipped": True,
                "revision_summary": "Rewrite failed. Keeping the assembled draft.",
                "summary": "Rewrite failed. Keeping the assembled draft.",
                "fixed_issues": [],
                "failure_reason": error_message,
            }
            workspace.set(node_def["output_key"], rewrite_result)
            pipeline = workspace.get("content_pipeline")
            if not isinstance(pipeline, dict):
                pipeline = {}
            pipeline["rewrite_attempted"] = True
            pipeline["rewrite_used"] = False
            pipeline["rewrite_failed"] = True
            pipeline["degraded"] = True
            workspace.set("content_pipeline", pipeline)

    def _normalize_review_result(self, node_id: str, data: dict[str, Any]) -> dict[str, Any]:
        reviewer = str(data.get("reviewer") or node_id).strip() or node_id
        issues = data.get("issues") if isinstance(data.get("issues"), list) else []
        rewrite_suggestions = (
            [str(item).strip() for item in data.get("rewrite_suggestions", []) if str(item).strip()]
            if isinstance(data.get("rewrite_suggestions"), list)
            else []
        )
        normalized_score = None
        raw_score = data.get("score")
        try:
            if raw_score is not None:
                normalized_score = max(0.0, min(1.0, float(raw_score)))
        except (TypeError, ValueError):
            normalized_score = None
        return {
            "reviewer": reviewer,
            "passed": data.get("passed"),
            "score": normalized_score,
            "summary": str(data.get("summary") or "").strip(),
            "issues": issues,
            "rewrite_suggestions": rewrite_suggestions,
            "failed": bool(data.get("failed")),
            "degraded": bool(data.get("degraded")),
            "error_message": data.get("error_message"),
        }

    def _normalize_rewrite_result(self, data: dict[str, Any]) -> dict[str, Any]:
        revised_content = str(
            data.get("revised_content_markdown")
            or data.get("content_markdown")
            or data.get("content")
            or ""
        ).strip()
        used_rewrite = data.get("used_rewrite")
        if not isinstance(used_rewrite, bool):
            used_rewrite = bool(revised_content)
        return {
            "used_rewrite": used_rewrite,
            "revised_content_markdown": revised_content,
            "revised_content_html": data.get("revised_content_html") or data.get("content_html"),
            "revision_summary": str(data.get("revision_summary") or data.get("summary") or "").strip(),
            "summary": str(data.get("revision_summary") or data.get("summary") or "").strip(),
            "fixed_issues": [
                str(item).strip()
                for item in data.get("fixed_issues", [])
                if str(item).strip()
            ] if isinstance(data.get("fixed_issues"), list) else [],
            "changed_sections": [
                str(item).strip()
                for item in data.get("changed_sections", [])
                if str(item).strip()
            ] if isinstance(data.get("changed_sections"), list) else [],
            "rewrite_failed": bool(data.get("rewrite_failed")),
            "rewrite_skipped": bool(data.get("rewrite_skipped")),
            "failure_reason": data.get("failure_reason"),
        }

    def _upsert_review_result(self, workspace: Workspace, review_result: dict[str, Any]) -> None:
        existing = workspace.get("review_results")
        review_results = existing if isinstance(existing, list) else []
        reviewer = review_result.get("reviewer")
        filtered = [
            item
            for item in review_results
            if not (isinstance(item, dict) and item.get("reviewer") == reviewer)
        ]
        filtered.append(review_result)
        workspace.set("review_results", filtered)

    async def _record_skipped_node(
        self,
        task_id: str,
        node_def: dict[str, Any],
        db: AsyncSession,
        reason: str,
    ) -> None:
        node_run = TaskNodeRunModel(
            task_id=task_id,
            node_id=node_def["node_id"],
            agent_id=node_def["agent_id"],
            status="skipped",
            error_message=reason,
            degraded=True,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            elapsed_seconds=0,
        )
        db.add(node_run)
        await db.flush()

    async def _resolve_system_prompt(
        self, agent_id: str, default_prompt: str, db: AsyncSession
    ) -> str:
        stmt = select(AgentModel.prompt_template).where(AgentModel.agent_id == agent_id)
        result = await db.execute(stmt)
        db_prompt = result.scalar_one_or_none()
        if db_prompt:
            logger.info("prompt_resolved", agent_id=agent_id, source="custom")
            return db_prompt
        logger.info("prompt_resolved", agent_id=agent_id, source="default")
        return default_prompt

    async def _mark_node_failed(
        self, node_run: TaskNodeRunModel, error_message: str, db: AsyncSession
    ) -> None:
        node_run.status = "failed"
        node_run.error_message = error_message
        await self._finalize_node(node_run, db)

    async def _finalize_node(self, node_run: TaskNodeRunModel, db: AsyncSession) -> None:
        if node_run.completed_at is None:
            node_run.completed_at = datetime.now(timezone.utc)
        if node_run.started_at and node_run.completed_at:
            node_run.elapsed_seconds = (node_run.completed_at - node_run.started_at).total_seconds()
        db.add(node_run)
        await db.flush()

    def _result_error_message(self, result: AgentResult) -> str:
        if not result.error:
            return "unknown agent failure"
        return str(result.error.get("message") or "unknown agent failure")

    def _summarize_output(self, output: dict | None) -> str:
        if not output:
            return ""
        keys = list(output.keys())
        if len(keys) <= 3:
            return f"keys: {', '.join(keys)}"
        return f"keys: {', '.join(keys[:3])}... ({len(keys)} total)"


orchestrator_engine = OrchestratorEngine()
