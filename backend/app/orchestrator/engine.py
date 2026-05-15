"""Workflow orchestrator with structured content pipeline support."""

from __future__ import annotations

import asyncio
import builtins
import sys
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
from app.models.tables import AgentModel, LLMProviderModel, TaskModel, TaskNodeRunModel
from app.orchestrator.broadcaster import broadcaster
from app.orchestrator.workspace import Workspace
from app.services.account_service import account_service
from app.services.article_assembler_service import article_assembler_service
from app.services.system_config_service import SystemConfigService

logger = get_logger(__name__)


def _safe_print(*args: object, sep: str = " ", end: str = "\n") -> None:
    text = sep.join(str(arg) for arg in args) + end
    try:
        builtins.print(*args, sep=sep, end=end)
    except UnicodeEncodeError:
        stream = sys.stdout
        encoding = getattr(stream, "encoding", None) or "utf-8"
        buffer = getattr(stream, "buffer", None)
        encoded = text.encode(encoding, errors="backslashreplace")
        if buffer is not None:
            buffer.write(encoded)
        else:
            stream.write(encoded.decode(encoding, errors="ignore"))


print = _safe_print

STRUCTURED_CONTENT_NODE_IDS = {
    "content_writing",
}

REVIEWER_NODE_IDS = set()

REWRITE_NODE_IDS = {
    "rewrite_agent",
}

QUALITY_GATE_NODE_IDS = {
    "audit",
}

POST_PROCESS_NODE_IDS = {
    "post_process_agent",
}

LEGACY_CONTENT_FALLBACK_NODE = {
    "node_id": "content_writing_fallback",
    "agent_id": "content_writer_agent",
    "name": "Legacy Content Writer Fallback",
    "timeout_seconds": 300,
    "input_mapping": {
        "profile": "profile",
        "topics": "topics",
        "titles": "titles",
        "hot_topics": "hot_topics",
        "account_context": "account_context",
        "ops_context": "ops_context",
        "selected_evidence": "selected_evidence",
        "evidence_summaries": "evidence_summaries",
        "citation_guardrails": "citation_guardrails",
    },
    "output_key": "content",
    "required": True,
}

DEFAULT_WORKFLOW_NODES = [
    {
        "node_id": "profile_parsing",
        "agent_id": "profile_agent",
        "name": "Profile Parsing",
        "input_mapping": {
            "positioning": "input.positioning",
            "content_platform": "account_context.content_platform",
            "account_context": "account_context",
        },
        "output_key": "profile",
        "required": True,
    },
    {
        "node_id": "hot_topic_analysis",
        "agent_id": "hot_topic_agent",
        "name": "Hot Topic Analysis",
        "timeout_seconds": 300,
        "input_mapping": {
            "profile": "profile",
            "account_context": "account_context",
            "ops_context": "ops_context",
            "query_plan": "query_plan",
            "source_candidates": "source_candidates",
            "reference_digest": "reference_digest",
            "selected_evidence": "selected_evidence",
            "evidence_summaries": "evidence_summaries",
            "citation_guardrails": "citation_guardrails",
        },
        "output_key": "hot_topics",
        "required": True,
    },
    {
        "node_id": "topic_planning",
        "agent_id": "topic_planner_agent",
        "name": "Topic Planning",
        "timeout_seconds": 300,
        "input_mapping": {
            "profile": "profile",
            "hot_topics": "hot_topics",
            "account_context": "account_context",
            "ops_context": "ops_context",
            "query_plan": "query_plan",
            "reference_digest": "reference_digest",
            "source_candidates": "source_candidates",
            "selected_evidence": "selected_evidence",
            "evidence_summaries": "evidence_summaries",
            "citation_guardrails": "citation_guardrails",
            "outline_seed": "outline_seed",
        },
        "output_key": "topic_bundle",
        "required": True,
    },
    {
        "node_id": "content_writing",
        "agent_id": "content_writer_agent",
        "name": "Content Writing",
        "timeout_seconds": 420,
        "input_mapping": {
            "profile": "profile",
            "topics": "topics",
            "titles": "titles",
            "hot_topics": "hot_topics",
            "account_context": "account_context",
            "ops_context": "ops_context",
            "query_plan": "query_plan",
            "reference_digest": "reference_digest",
            "source_candidates": "source_candidates",
            "selected_evidence": "selected_evidence",
            "evidence_summaries": "evidence_summaries",
            "citation_guardrails": "citation_guardrails",
        },
        "output_key": "content",
        "required": True,
    },
    {
        "node_id": "audit",
        "agent_id": "audit_agent",
        "name": "Audit (Single Gate)",
        "input_mapping": {
            "titles": "titles",
            "content": "content",
            "profile": "profile",
            "account_context": "account_context",
            "selected_evidence": "selected_evidence",
            "citation_guardrails": "citation_guardrails",
        },
        "output_key": "audit_result",
        "required": True,
    },
    {
        "node_id": "rewrite_agent",
        "agent_id": "rewrite_agent",
        "name": "Rewrite Agent",
        "timeout_seconds": 600,
        "input_mapping": {
            "titles": "titles",
            "topics": "topics",
            "assembled_article": "assembled_article",
            "content": "content",
            "audit_result": "audit_result",
            "account_context": "account_context",
            "ops_context": "ops_context",
            "query_plan": "query_plan",
            "reference_digest": "reference_digest",
            "source_candidates": "source_candidates",
            "selected_evidence": "selected_evidence",
            "evidence_summaries": "evidence_summaries",
            "citation_guardrails": "citation_guardrails",
        },
        "output_key": "rewrite_result",
        "required": False,
    },
    {
        "node_id": "post_process_agent",
        "agent_id": "post_process_agent",
        "name": "Post-process Agent",
        "input_mapping": {
            "content": "content",
            "assembled_article": "assembled_article",
            "rewrite_result": "rewrite_result",
            "audit_result": "audit_result",
            "draft_quality_gate": "draft_quality_gate",
            "titles": "titles",
            "topics": "topics",
            "account_context": "account_context",
            "source_candidates": "source_candidates",
            "reference_digest": "reference_digest",
        },
        "output_key": "post_process_result",
        "required": False,
    },
    {
        "node_id": "account_ops_finalize",
        "agent_id": "account_ops_finalize_service",
        "name": "Account Ops Finalize",
        "executor": "service",
        "service": "account_ops_finalize",
        "input_mapping": {
            "ops_context": "ops_context",
            "audit_result": "audit_result",
            "post_process_result": "post_process_result",
            "content_pipeline": "content_pipeline",
        },
        "output_key": "account_ops_result",
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
        quality_gate_blocked = False
        stage_envelopes: list[dict[str, Any]] = []

        account_context = await account_service.get_account_context(task.account_id, db)
        if account_context:
            workspace.set("account_context", account_context)
            logger.info("account_context_injected", account_id=task.account_id)

        ops_context = None
        if isinstance(task.input_data, dict):
            candidate = task.input_data.get("ops_context")
            if isinstance(candidate, dict):
                ops_context = candidate
        if ops_context:
            workspace.set("ops_context", ops_context)
            logger.info(
                "ops_context_injected",
                account_id=task.account_id,
                task_id=task.id,
                effective_mode=(ops_context.get("run_strategy") or {}).get("effective_mode"),
            )

        if isinstance(task.input_data, dict):
            explicit_payload = self._extract_explicit_input_payload(task.input_data)
            for key, value in explicit_payload.items():
                workspace.set(key, value)
            if explicit_payload:
                logger.info(
                    "explicit_creation_input_injected",
                    task_id=task.id,
                    account_id=task.account_id,
                    keys=sorted(explicit_payload.keys()),
                    selection_session_id=explicit_payload.get("selection_session_id"),
                )

        if task.status != "running":
            task.status = "running"
        task.started_at = task.started_at or datetime.now(timezone.utc)
        db.add(task)
        await db.flush()
        logger.info(
            "orchestrator_run_started",
            task_id=task.id,
            account_id=task.account_id,
            trace_id=trace_id,
            provider=self._provider_hint(),
            model=self._model_hint(),
            timeout=settings.agent_timeout,
        )

        for idx, node_def in enumerate(DEFAULT_WORKFLOW_NODES):
            node_id = node_def["node_id"]
            agent_runtime = None
            if structured_pipeline_degraded and node_id in STRUCTURED_CONTENT_NODE_IDS:
                await self._record_skipped_node(task.id, node_def, db, "legacy_content_fallback")
                continue
            ops_context = workspace.get("ops_context")
            if (
                quality_gate_blocked
                and node_id in POST_PROCESS_NODE_IDS
                and not self._allow_manual_post_process_after_quality_gate(ops_context)
                and not self._allow_review_only_post_process(workspace)
            ):
                await self._record_skipped_node(task.id, node_def, db, "draft_quality_gate_blocked")
                continue
            run_strategy = self._extract_run_strategy(ops_context)
            strategy_skip_reason = self._strategy_skip_reason(node_id, run_strategy)
            if strategy_skip_reason:
                await self._record_skipped_node(task.id, node_def, db, strategy_skip_reason)
                continue
            if node_id in REWRITE_NODE_IDS and not self._should_run_rewrite(workspace):
                await self._record_skipped_node(task.id, node_def, db, "audit_skip_rewrite")
                continue
            if node_def.get("executor") != "service":
                agent = agent_registry.get(node_def["agent_id"])
                agent_runtime = await self._resolve_agent_runtime(
                    node_def["agent_id"],
                    agent.default_system_prompt,
                    db,
                )

            node_run = TaskNodeRunModel(
                task_id=task.id,
                node_id=node_id,
                agent_id=node_def["agent_id"],
                status="running",
                started_at=datetime.now(timezone.utc),
                model_used=(agent_runtime or {}).get("model") or self._model_used_for_node(node_def),
            )
            db.add(node_run)
            await db.flush()

            agent_input = workspace.extract_for_agent(node_def["input_mapping"])
            node_run.input_data = agent_input
            db.add(node_run)
            await db.flush()
            await db.commit()

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
            logger.info(
                "node_execution_started",
                task_id=task.id,
                account_id=task.account_id,
                node_id=node_id,
                agent_id=node_def["agent_id"],
                trace_id=trace_id,
                provider=(agent_runtime or {}).get("provider") or self._provider_hint_for_node(node_def),
                model=(agent_runtime or {}).get("model") or self._model_used_for_node(node_def),
                timeout=self._node_timeout_seconds(node_def) if node_def.get("executor") != "service" else None,
            )

            try:
                result = await self._execute_node(
                    node_def,
                    agent_input,
                    workspace.snapshot(),
                    trace_id,
                    db,
                    task.id,
                    task.account_id,
                    agent_runtime,
                )
                runtime_trace = self._extract_runtime_trace(result)
                if result.is_success:
                    self._store_node_result(workspace, node_def, result.data or {})
                    self._apply_runtime_trace_to_node_run(node_run, runtime_trace)
                    if node_id in QUALITY_GATE_NODE_IDS:
                        gate_result = workspace.get("audit_result")
                        quality_gate_blocked = isinstance(gate_result, dict) and gate_result.get("passed") is False
                    if node_id == "audit" and self._is_audit_blocker(workspace.get("audit_result")):
                        structured_pipeline_degraded = True
                        workspace.set("review_only_mode", True)
                    node_run.status = "completed"
                    node_run.output_data = self._merge_runtime_output(result.data, runtime_trace)

                    # 计算执行时长
                    elapsed = self._elapsed_seconds(
                        started_at=node_run.started_at,
                        completed_at=node_run.completed_at,
                    )

                    # 终端详细日志输出
                    print(f"\n{'='*60}")
                    print(f"[OK] Node completed: {node_def['name']} ({node_id})")
                    print(f"   智能体: {node_def['agent_id']}")
                    print(f"   状态: COMPLETED")
                    print(f"   耗时: {elapsed:.2f}s" if elapsed else "   耗时: N/A")
                    print(f"   降级: {'是' if node_run.degraded else '否'}")

                    # 输出关键结果摘要
                    if result.data:
                        if "title" in result.data:
                            print(f"   标题: {result.data['title'][:50]}...")
                        if "outline" in result.data:
                            outline = result.data["outline"]
                            if isinstance(outline, list):
                                print(f"   大纲: {len(outline)} 个章节")
                            elif isinstance(outline, str):
                                print(f"   大纲: {outline[:50]}...")
                        if "sections" in result.data:
                            sections = result.data["sections"]
                            if isinstance(sections, list):
                                print(f"   正文: {len(sections)} 个段落")
                        if "content" in result.data:
                            content = result.data["content"]
                            if isinstance(content, str):
                                print(f"   内容长度: {len(content)} 字符")
                    print(f"{'='*60}\n")

                    logger.info(
                        "node_execution_completed",
                        task_id=task.id,
                        node_id=node_id,
                        agent_id=node_def["agent_id"],
                        status="completed",
                        elapsed_seconds=elapsed,
                        degraded=node_run.degraded,
                    )
                else:
                    error_message = self._result_error_message(result)
                    runtime_trace = self._extract_runtime_trace(
                        result,
                        error_class="execution_error",
                        error_message=error_message,
                    )

                    # 计算执行时长
                    elapsed = self._elapsed_seconds(
                        started_at=node_run.started_at,
                        completed_at=node_run.completed_at,
                    )

                    # 终端详细日志输出 - 失败
                    print(f"\n{'='*60}")
                    print(f"[FAIL] Node failed: {node_def['name']} ({node_id})")
                    print(f"   智能体: {node_def['agent_id']}")
                    print(f"   状态: FAILED")
                    print(f"   耗时: {elapsed:.2f}s" if elapsed else "   耗时: N/A")
                    print(f"   错误: {error_message[:100]}...")
                    print(f"{'='*60}\n")

                    if node_id in STRUCTURED_CONTENT_NODE_IDS:
                        await self._mark_node_failed(node_run, error_message, db, runtime_trace=runtime_trace)
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
                        fallback_trace = self._merge_runtime_trace(
                            runtime_trace,
                            self._extract_runtime_trace(fallback_result, fallback_used=True),
                        )
                        self._store_node_result(workspace, node_def, fallback_result.data or {})
                        node_run.status = "completed"
                        self._apply_runtime_trace_to_node_run(node_run, fallback_trace)
                        node_run.output_data = self._merge_runtime_output(fallback_result.data, fallback_trace)
                        node_run.degraded = True
                    elif node_def.get("required", True):
                        await self._mark_node_failed(node_run, error_message, db, runtime_trace=runtime_trace)
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
                        self._apply_runtime_trace_to_node_run(node_run, runtime_trace)
                        node_run.output_data = self._merge_runtime_output(None, runtime_trace)
                        self._store_optional_node_failure(workspace, node_def, error_message)
                        await broadcaster.broadcast(
                            task.id,
                            "node_error",
                            {"node_id": node_id, "error": error_message},
                        )
            except asyncio.TimeoutError:
                error_message = f"agent {node_def['agent_id']} timed out"
                timeout_trace = {
                    "provider": (agent_runtime or {}).get("provider") or self._provider_hint_for_node(node_def),
                    "model": (agent_runtime or {}).get("model") or self._model_used_for_node(node_def),
                    "timeout_seconds": self._node_timeout_seconds(node_def),
                    "retry_count": 0,
                    "error_class": "timeout",
                    "error_message": error_message,
                }

                # 计算执行时长
                elapsed = self._elapsed_seconds(started_at=node_run.started_at)

                # 终端详细日志输出 - 超时
                print(f"\n{'='*60}")
                print(f"[TIMEOUT] Node timed out: {node_def['name']} ({node_id})")
                print(f"   智能体: {node_def['agent_id']}")
                print(f"   状态: TIMEOUT")
                print(f"   已运行: {elapsed:.2f}s" if elapsed else "   已运行: N/A")
                print(f"   超时限制: {self._node_timeout_seconds(node_def)}s")
                print(f"   错误: {error_message}")
                print(f"{'='*60}\n")

                fallback_result = await self._execute_agent_fallback(
                    node_def["agent_id"],
                    AgentTimeoutError(node_def["agent_id"]),
                    agent_input,
                )
                if fallback_result and fallback_result.is_success:
                    fallback_trace = self._merge_runtime_trace(
                        timeout_trace,
                        self._extract_runtime_trace(fallback_result, fallback_used=True),
                    )
                    self._store_node_result(workspace, node_def, fallback_result.data or {})
                    node_run.status = "completed"
                    self._apply_runtime_trace_to_node_run(node_run, fallback_trace)
                    node_run.output_data = self._merge_runtime_output(fallback_result.data, fallback_trace)
                    node_run.degraded = True
                    if node_id in STRUCTURED_CONTENT_NODE_IDS:
                        structured_pipeline_degraded = True
                    logger.warning(
                        "node_timeout_fallback_used",
                        task_id=task.id,
                        account_id=task.account_id,
                        node_id=node_id,
                        agent_id=node_def["agent_id"],
                        timeout_seconds=self._node_timeout_seconds(node_def),
                    )
                elif node_id in STRUCTURED_CONTENT_NODE_IDS:
                    await self._mark_node_failed(node_run, error_message, db, runtime_trace=timeout_trace)
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
                elif node_def.get("required", True):
                    await self._mark_node_failed(node_run, error_message, db, runtime_trace=timeout_trace)
                    await broadcaster.broadcast(
                        task.id,
                        "node_error",
                        {"node_id": node_id, "error": error_message},
                    )
                    raise AgentTimeoutError(node_def["agent_id"])
                else:
                    node_run.status = "failed"
                    node_run.error_message = error_message
                    node_run.degraded = True
                    self._apply_runtime_trace_to_node_run(node_run, timeout_trace)
                    node_run.output_data = self._merge_runtime_output(None, timeout_trace)
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
                unexpected_trace = {
                    "provider": (agent_runtime or {}).get("provider") or self._provider_hint_for_node(node_def),
                    "model": (agent_runtime or {}).get("model") or self._model_used_for_node(node_def),
                    "retry_count": 0,
                    "error_class": "unexpected_exception",
                    "error_message": error_message,
                }
                if node_id in STRUCTURED_CONTENT_NODE_IDS:
                    await self._mark_node_failed(node_run, error_message, db, runtime_trace=unexpected_trace)
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
                    await self._mark_node_failed(node_run, error_message, db, runtime_trace=unexpected_trace)
                    await broadcaster.broadcast(
                        task.id,
                        "node_error",
                        {"node_id": node_id, "error": error_message},
                    )
                    raise AgentExecutionError(node_def["agent_id"], error_message)
                node_run.status = "failed"
                node_run.error_message = error_message
                node_run.degraded = True
                self._apply_runtime_trace_to_node_run(node_run, unexpected_trace)
                node_run.output_data = self._merge_runtime_output(None, unexpected_trace)
                self._store_optional_node_failure(workspace, node_def, error_message)
                await broadcaster.broadcast(
                    task.id,
                    "node_error",
                    {"node_id": node_id, "error": error_message},
                )

            await self._finalize_node(node_run, db)
            node_stage = self._extract_node_stage_envelope(node_run)
            if node_stage:
                stage_envelopes.append(node_stage)
            logger.info(
                "node_execution_finished",
                task_id=task.id,
                account_id=task.account_id,
                node_id=node_id,
                agent_id=node_def["agent_id"],
                trace_id=trace_id,
                status=node_run.status,
                degraded=node_run.degraded,
                elapsed_seconds=node_run.elapsed_seconds,
                provider=self._provider_hint_from_model_used(node_run.model_used),
                model=node_run.model_used,
            )
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
        result_data = self._inject_execution_meta(
            result_data=result_data,
            stage_envelopes=stage_envelopes,
            degraded=structured_pipeline_degraded,
            review_only=bool(workspace.get("review_only_mode")),
            task_id=task.id,
        )
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        task.result_data = result_data
        task.total_tokens = total_tokens
        task.elapsed_seconds = self._elapsed_seconds(
            started_at=task.started_at,
            completed_at=task.completed_at,
        )
        db.add(task)
        await db.flush()

        # 任务完成 - 终端汇总输出
        print(f"\n{'='*80}")
        print(f"[DONE] Task completed: {task.id}")
        print(f"   状态: COMPLETED")
        print(f"   总耗时: {task.elapsed_seconds:.2f}s ({task.elapsed_seconds/60:.1f} 分钟)")
        print(f"   总 Token: {total_tokens:,}")
        print(f"   降级模式: {'是' if structured_pipeline_degraded else '否'}")

        # 输出关键结果
        if result_data:
            if "title" in result_data:
                print(f"   标题: {result_data['title']}")
            if "content" in result_data:
                content = result_data.get("content", "")
                print(f"   内容长度: {len(content):,} 字符")
            if "sections" in result_data:
                sections = result_data.get("sections", [])
                print(f"   段落数: {len(sections)}")
        print(f"{'='*80}\n")

        logger.info(
            "workflow_execution_completed",
            task_id=task.id,
            account_id=task.account_id,
            status="completed",
            elapsed_seconds=task.elapsed_seconds,
            total_tokens=total_tokens,
            degraded=structured_pipeline_degraded,
        )

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
        task_id: str,
        account_id: str | None,
        agent_runtime: dict[str, Any] | None = None,
    ) -> AgentResult:
        if node_def.get("executor") == "service":
            return await self._execute_service_node(
                node_def,
                input_data,
                task_id=task_id,
                account_id=account_id,
            )

        agent = agent_registry.get(node_def["agent_id"])
        runtime = agent_runtime or await self._resolve_agent_runtime(
            node_def["agent_id"],
            agent.default_system_prompt,
            db,
        )
        enriched_context = dict(context)
        enriched_context["system_prompt"] = runtime["system_prompt"]
        enriched_context["agent_model_config"] = runtime.get("model_config")
        enriched_context["db"] = db
        enriched_context["task_id"] = task_id
        enriched_context["account_id"] = account_id
        enriched_context["trace_id"] = trace_id
        enriched_context["node_timeout_seconds"] = self._node_timeout_seconds(node_def)
        if node_def.get("node_id") in POST_PROCESS_NODE_IDS:
            enriched_context["image_generation_config"] = await SystemConfigService(db).get_image_generation_config()
        run_strategy = self._extract_run_strategy(context.get("ops_context"))
        enriched_context["runtime_policy"] = {
            "max_retries": settings.llm_max_retries,
            "retry_backoff_seconds": settings.llm_retry_backoff_seconds,
            "prefer_high_cost_model": node_def["node_id"] in set(run_strategy.get("high_cost_model_nodes") or []),
        }
        result = await self._execute_agent_with_timeout(
            agent,
            input_data,
            enriched_context,
            trace_id,
            timeout_seconds=self._node_timeout_seconds(node_def),
        )
        if result.runtime_trace is None and isinstance(enriched_context.get("_agent_runtime_trace"), dict):
            result.runtime_trace = dict(enriched_context.get("_agent_runtime_trace") or {})
        return result

    async def _execute_service_node(
        self,
        node_def: dict[str, Any],
        input_data: dict[str, Any],
        *,
        task_id: str | None = None,
        account_id: str | None = None,
    ) -> AgentResult:
        if node_def.get("service") == "account_ops_finalize":
            audit_result = input_data.get("audit_result") if isinstance(input_data.get("audit_result"), dict) else {}
            post_process_result = (
                input_data.get("post_process_result")
                if isinstance(input_data.get("post_process_result"), dict)
                else {}
            )
            ops_context = input_data.get("ops_context") if isinstance(input_data.get("ops_context"), dict) else {}
            pipeline = input_data.get("content_pipeline") if isinstance(input_data.get("content_pipeline"), dict) else {}
            result_payload = {
                "final_status": "ready_for_review" if bool(post_process_result) else "content_generated",
                "audit_passed": bool(audit_result.get("passed")),
                "audit_risk_level": audit_result.get("risk_level"),
                "ops_notes": (ops_context.get("ops_notes") if isinstance(ops_context, dict) else []) or [],
                "degraded": bool(pipeline.get("degraded")),
            }
            return AgentResult(
                status="success",
                agent_name=node_def["agent_id"],
                data=result_payload,
            )

        if node_def.get("service") == "draft_quality_gate":
            from app.services.draft_quality_gate_service import draft_quality_gate_service

            gate_result = await draft_quality_gate_service.evaluate_result(
                input_data,
                task_id=task_id,
                account_id=account_id,
            )
            return AgentResult(
                status="success",
                agent_name=node_def["agent_id"],
                data=gate_result,
            )

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
        self,
        agent: BaseAgent,
        input_data: dict,
        context: dict,
        trace_id: str,
        *,
        timeout_seconds: int,
    ) -> AgentResult:
        return await asyncio.wait_for(
            agent.execute(input_data, context),
            timeout=timeout_seconds,
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
            trace_id=trace_id,
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
        await db.commit()

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
            result = await self._execute_node(
                node_def,
                agent_input,
                workspace.snapshot(),
                trace_id,
                db,
                task_id,
                None,
            )
            runtime_trace = self._extract_runtime_trace(result)
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
                runtime_trace = self._merge_runtime_trace(
                    runtime_trace,
                    self._extract_runtime_trace(fallback_result, fallback_used=True),
                )

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
            self._apply_runtime_trace_to_node_run(node_run, runtime_trace)
            node_run.output_data = self._merge_runtime_output(legacy_content, runtime_trace)
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
            await self._mark_node_failed(
                node_run,
                reason,
                db,
                runtime_trace={
                    "error_class": "legacy_content_fallback_failed",
                    "error_message": reason,
                    "retry_count": 0,
                    "fallback_used": True,
                },
            )
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
        if node_id == "hot_topic_analysis":
            workspace.set(node_def["output_key"], data)
            for key in (
                "query_plan",
                "source_candidates",
                "source_snippets",
                "reference_digest",
                "external_evidence",
                "fetched_evidence",
                "selected_evidence",
                "evidence_summaries",
                "citation_guardrails",
            ):
                if key in data:
                    workspace.set(key, data.get(key))
            return
        if node_id == "topic_planning":
            topic_payload = data if isinstance(data, dict) else {}
            workspace.set(node_def["output_key"], topic_payload)
            if "topics" in topic_payload:
                workspace.set("topics", {"topics": topic_payload.get("topics") or []})
            if "titles" in topic_payload:
                workspace.set("titles", topic_payload.get("titles") or {})
            elif isinstance(topic_payload.get("topics"), list):
                generated_titles = []
                for item in topic_payload.get("topics", []):
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title") or "").strip()
                    if title:
                        generated_titles.append({"title": title, "confidence": item.get("estimated_appeal", 0.6)})
                selected_title = generated_titles[0]["title"] if generated_titles else ""
                workspace.set(
                    "titles",
                    {
                        "selected_title": selected_title,
                        "titles": generated_titles,
                        "candidates": generated_titles,
                    },
                )
            return
        if node_id == "content_writing":
            content_payload = data if isinstance(data, dict) else {}
            workspace.set(node_def["output_key"], content_payload)
            workspace.set(
                "assembled_article",
                article_assembler_service.extract_assembled_article_payload(
                    {
                        "content": content_payload,
                        "titles": workspace.get("titles"),
                        "topics": workspace.get("topics"),
                    }
                ),
            )
            workspace.set(
                "content",
                article_assembler_service.extract_article_payload(
                    {
                        "content": content_payload,
                        "titles": workspace.get("titles"),
                        "topics": workspace.get("topics"),
                    }
                ),
            )
            workspace.set(
                "content_pipeline",
                {
                    "version": "phase7-unified-v1",
                    "used_structured_pipeline": True,
                    "fallback_to_content_writer": False,
                    "degraded": False,
                },
            )
            return
        if node_id == "audit":
            audit_result = dict(data or {})
            workspace.set(node_def["output_key"], audit_result)
            workspace.set(
                "draft_quality_gate",
                {
                    "passed": bool(audit_result.get("passed")),
                    "status": "passed" if bool(audit_result.get("passed")) else "blocked",
                    "source": "single_audit_gate",
                    "risk_level": audit_result.get("risk_level"),
                },
            )
            pipeline = workspace.get("content_pipeline")
            if not isinstance(pipeline, dict):
                pipeline = {}
            pipeline["quality_gate_checked"] = True
            pipeline["quality_gate_passed"] = bool(audit_result.get("passed"))
            pipeline["quality_gate_status"] = "passed" if bool(audit_result.get("passed")) else "blocked"
            pipeline["single_gate_mode"] = True
            if audit_result.get("passed") is False:
                pipeline["degraded"] = True
            workspace.set("content_pipeline", pipeline)
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
            review_result = self._normalize_review_result(node_id, data)
            workspace.set(node_def["output_key"], review_result)
            self._upsert_review_result(workspace, review_result)
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
        if node_id in QUALITY_GATE_NODE_IDS:
            gate_result = dict(data or {})
            workspace.set(node_def["output_key"], gate_result)
            pipeline = workspace.get("content_pipeline")
            if not isinstance(pipeline, dict):
                pipeline = {}
            pipeline["quality_gate_checked"] = True
            pipeline["quality_gate_passed"] = bool(gate_result.get("passed"))
            pipeline["quality_gate_status"] = gate_result.get("status")
            if gate_result.get("passed") is False:
                pipeline["post_process_skipped"] = True
                pipeline["degraded"] = True
            workspace.set("content_pipeline", pipeline)
            return
        if node_id in POST_PROCESS_NODE_IDS:
            post_process_result = self._normalize_post_process_result(data)
            workspace.set(node_def["output_key"], post_process_result)
            pipeline = workspace.get("content_pipeline")
            if not isinstance(pipeline, dict):
                pipeline = {}
            pipeline["post_process_attempted"] = True
            pipeline["post_process_used"] = bool(post_process_result.get("used_post_process"))
            pipeline["ready_for_review"] = bool(
                (post_process_result.get("wechat_publish_format") or {}).get("ready_for_review")
            )
            workspace.set("content_pipeline", pipeline)
            if post_process_result.get("used_post_process") and post_process_result.get("final_content_markdown"):
                current_content = article_assembler_service.extract_article_payload(
                    {
                        "assembled_article": workspace.get("assembled_article"),
                        "content": workspace.get("content"),
                        "rewrite_result": workspace.get("rewrite_result"),
                        "titles": workspace.get("titles"),
                        "topics": workspace.get("topics"),
                        "outline_plan": workspace.get("outline_plan"),
                        "section_drafts": workspace.get("section_drafts"),
                    }
                )
                final_content = dict(current_content)
                final_markdown = str(post_process_result.get("final_content_markdown") or "").strip()
                final_content["content_markdown"] = final_markdown
                final_html = post_process_result.get("final_content_html")
                if final_html:
                    final_content["content_html"] = final_html
                final_content["word_count"] = article_assembler_service.count_words(final_markdown)
                workspace.set("content", final_content)
            return
        if node_id == "account_ops_finalize":
            workspace.set(node_def["output_key"], data if isinstance(data, dict) else {})
            return
        workspace.set(node_def["output_key"], data)

    def _store_optional_node_failure(
        self, workspace: Workspace, node_def: dict[str, Any], error_message: str
    ) -> None:
        node_id = node_def["node_id"]
        if node_id in REVIEWER_NODE_IDS:
            review_result = {
                "reviewer": node_id,
                "passed": False,
                "score": None,
                "summary": f"{node_def['name']} failed. Keeping the assembled article without reviewer guidance.",
                "issues": [],
                "rewrite_suggestions": [],
                "failed": True,
                "degraded": True,
                "error_message": error_message,
            }
            workspace.set(node_def["output_key"], review_result)
            self._upsert_review_result(workspace, review_result)
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

    def _normalize_post_process_result(self, data: dict[str, Any]) -> dict[str, Any]:
        final_content = str(
            data.get("final_content_markdown")
            or data.get("content_markdown")
            or data.get("content")
            or ""
        ).strip()
        used_post_process = data.get("used_post_process")
        if not isinstance(used_post_process, bool):
            used_post_process = bool(final_content)
        return {
            "used_post_process": used_post_process,
            "post_process_skipped": bool(data.get("post_process_skipped")),
            "skip_reason": data.get("skip_reason"),
            "layout_template": data.get("layout_template") if isinstance(data.get("layout_template"), dict) else None,
            "template_options": [
                item
                for item in data.get("template_options", [])
                if isinstance(item, dict)
            ] if isinstance(data.get("template_options"), list) else [],
            "layout_blocks": [
                item
                for item in data.get("layout_blocks", [])
                if isinstance(item, dict)
            ] if isinstance(data.get("layout_blocks"), list) else [],
            "final_content_markdown": final_content,
            "final_content_html": data.get("final_content_html") or data.get("content_html"),
            "polishing_summary": str(data.get("polishing_summary") or data.get("summary") or "").strip(),
            "layout_notes": [
                str(item).strip()
                for item in data.get("layout_notes", [])
                if str(item).strip()
            ] if isinstance(data.get("layout_notes"), list) else [],
            "image_slots": [
                item
                for item in data.get("image_slots", [])
                if isinstance(item, dict)
            ] if isinstance(data.get("image_slots"), list) else [],
            "layout_artifacts": data.get("layout_artifacts") if isinstance(data.get("layout_artifacts"), dict) else {},
            "cover_image_prompt": str(data.get("cover_image_prompt") or "").strip(),
            "wechat_publish_format": data.get("wechat_publish_format") if isinstance(data.get("wechat_publish_format"), dict) else {},
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

    def _extract_run_strategy(self, ops_context: Any) -> dict[str, Any]:
        if isinstance(ops_context, dict):
            run_strategy = ops_context.get("run_strategy")
            if isinstance(run_strategy, dict):
                return run_strategy
        return {}
    def _allow_manual_post_process_after_quality_gate(self, ops_context: Any) -> bool:
        if not isinstance(ops_context, dict):
            return False
        run_strategy = self._extract_run_strategy(ops_context)
        if run_strategy.get("allow_post_process") is False:
            return False
        trigger = ops_context.get("trigger")
        if isinstance(trigger, dict):
            source = str(trigger.get("source") or "").strip().lower()
            if source == "manual":
                return True
        effective_mode = str(run_strategy.get("effective_mode") or "").strip().lower()
        return effective_mode == "manual"

    def _allow_review_only_post_process(self, workspace: Workspace) -> bool:
        return bool(workspace.get("review_only_mode"))

    def _strategy_skip_reason(self, node_id: str, run_strategy: dict[str, Any]) -> str | None:
        if not run_strategy:
            return None

        allow_rewrite = run_strategy.get("allow_rewrite")
        allow_post_process = run_strategy.get("allow_post_process")

        if node_id in REWRITE_NODE_IDS and allow_rewrite is False:
            return "run_strategy_disabled_rewrite"
        if node_id in POST_PROCESS_NODE_IDS and allow_post_process is False:
            return "run_strategy_disabled_post_process"
        return None

    def _should_run_rewrite(self, workspace: Workspace) -> bool:
        audit_result = workspace.get("audit_result")
        if not isinstance(audit_result, dict):
            return False
        if self._is_audit_blocker(audit_result):
            return False
        if str(audit_result.get("risk_level") or "").strip().lower() == "medium":
            return True
        rewrite_required = audit_result.get("rewrite_required")
        if isinstance(rewrite_required, bool):
            return rewrite_required
        if bool(audit_result.get("passed")):
            return False
        return True

    def _is_audit_blocker(self, audit_result: Any) -> bool:
        if not isinstance(audit_result, dict):
            return False
        if audit_result.get("publish_decision") == "blocker":
            return True
        if str(audit_result.get("risk_level") or "").strip().lower() == "high":
            return True
        issues = audit_result.get("issues")
        if isinstance(issues, list):
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                if str(issue.get("severity") or "").strip().lower() == "high":
                    return True
        return False

    def _extract_runtime_trace(
        self,
        result: AgentResult | None = None,
        *,
        error_class: str | None = None,
        error_message: str | None = None,
        fallback_used: bool | None = None,
    ) -> dict[str, Any] | None:
        trace = dict(result.runtime_trace) if result and isinstance(result.runtime_trace, dict) else {}
        if fallback_used is not None:
            trace["fallback_used"] = fallback_used
        if error_class and not trace.get("error_class"):
            trace["error_class"] = error_class
        if error_message and not trace.get("error_message"):
            trace["error_message"] = error_message
        return trace or None

    def _merge_runtime_trace(
        self,
        primary: dict[str, Any] | None,
        secondary: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not primary and not secondary:
            return None
        merged: dict[str, Any] = {}
        if primary:
            merged.update(primary)
        if secondary:
            merged.update(secondary)
        return merged

    def _apply_runtime_trace_to_node_run(
        self,
        node_run: TaskNodeRunModel,
        runtime_trace: dict[str, Any] | None,
    ) -> None:
        if not runtime_trace:
            return

        prompt_tokens = runtime_trace.get("prompt_tokens")
        completion_tokens = runtime_trace.get("completion_tokens")
        model_used = runtime_trace.get("model")

        if isinstance(prompt_tokens, int):
            node_run.prompt_tokens = prompt_tokens
        if isinstance(completion_tokens, int):
            node_run.completion_tokens = completion_tokens
        if isinstance(model_used, str) and model_used.strip():
            node_run.model_used = model_used.strip()

    def _merge_runtime_output(
        self,
        output_data: dict[str, Any] | None,
        runtime_trace: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not runtime_trace:
            return output_data
        payload = dict(output_data) if isinstance(output_data, dict) else {}
        payload["_runtime"] = runtime_trace
        return payload

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
            output_data={
                "_runtime": {
                    "error_class": "skipped",
                    "error_message": reason,
                    "skip_reason": reason,
                    "retry_count": 0,
                    "fallback_used": False,
                }
            },
        )
        db.add(node_run)
        await db.flush()

    async def _resolve_agent_runtime(
        self, agent_id: str, default_prompt: str, db: AsyncSession
    ) -> dict[str, Any]:
        stmt = select(AgentModel.prompt_template, AgentModel.model_config_data).where(AgentModel.agent_id == agent_id)
        result = await db.execute(stmt)
        row = result.one_or_none()
        db_prompt = row[0] if row else None
        model_config_data = row[1] if row else None

        if db_prompt:
            logger.info("prompt_resolved", agent_id=agent_id, source="custom")
        else:
            logger.info("prompt_resolved", agent_id=agent_id, source="default")

        model_config = await self._resolve_agent_model_config(model_config_data, db)
        return {
            "system_prompt": db_prompt or default_prompt,
            "model_config": model_config,
            "provider": model_config["provider_id"] if model_config else self._provider_hint(),
            "model": model_config["model"] if model_config else self._model_hint(),
        }

    async def _resolve_agent_model_config(
        self, model_config_data: dict[str, Any] | None, db: AsyncSession
    ) -> dict[str, Any] | None:
        if not isinstance(model_config_data, dict) or not model_config_data:
            return None

        provider_id = str(model_config_data.get("provider_id") or "").strip()
        if not provider_id:
            return None

        provider_result = await db.execute(
            select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id)
        )
        provider = provider_result.scalar_one_or_none()

        raw_model = str(
            model_config_data.get("model")
            or model_config_data.get("default_model")
            or (provider.default_model if provider and provider.default_model else "")
        ).strip()
        if not raw_model:
            raw_model = settings.llm_model_name.strip()

        return {
            "provider_id": provider_id,
            "model": BaseAgent._normalize_model_name(provider_id, raw_model),
            "api_key": (provider.api_key if provider and provider.api_key else None) or settings.llm_api_key,
            "base_url": (provider.base_url if provider and provider.base_url else None) or settings.llm_api_base_url,
            "timeout": (provider.timeout if provider and provider.timeout else None) or settings.llm_timeout,
        }

    async def _mark_node_failed(
        self,
        node_run: TaskNodeRunModel,
        error_message: str,
        db: AsyncSession,
        *,
        runtime_trace: dict[str, Any] | None = None,
    ) -> None:
        node_run.status = "failed"
        node_run.error_message = error_message
        self._apply_runtime_trace_to_node_run(node_run, runtime_trace)
        node_run.output_data = self._merge_runtime_output(node_run.output_data, runtime_trace)
        await self._finalize_node(node_run, db)

    async def _finalize_node(self, node_run: TaskNodeRunModel, db: AsyncSession) -> None:
        if node_run.completed_at is None:
            node_run.completed_at = datetime.now(timezone.utc)
        node_run.elapsed_seconds = self._elapsed_seconds(
            started_at=node_run.started_at,
            completed_at=node_run.completed_at,
        )
        envelope = self._build_stage_envelope(node_run)
        payload = dict(node_run.output_data) if isinstance(node_run.output_data, dict) else {}
        payload["stage_envelope"] = envelope
        node_run.output_data = payload
        db.add(node_run)
        await db.flush()

    def _ensure_utc(self, dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _node_timeout_seconds(self, node_def: dict[str, Any]) -> int:
        configured = node_def.get("timeout_seconds")
        if isinstance(configured, (int, float)) and configured > 0:
            return int(configured)
        return int(settings.agent_timeout)

    def _elapsed_seconds(
        self,
        *,
        started_at: datetime | None,
        completed_at: datetime | None = None,
    ) -> float | None:
        started = self._ensure_utc(started_at)
        if started is None:
            return None

        completed = self._ensure_utc(completed_at) or datetime.now(timezone.utc)
        return max((completed - started).total_seconds(), 0.0)

    def _build_stage_envelope(self, node_run: TaskNodeRunModel) -> dict[str, Any]:
        runtime = {}
        if isinstance(node_run.output_data, dict) and isinstance(node_run.output_data.get("_runtime"), dict):
            runtime = dict(node_run.output_data.get("_runtime") or {})
        status = node_run.status or "failed"
        severity = "none"
        if status in {"failed", "cancelled"}:
            severity = "blocker"
        elif node_run.degraded:
            severity = "major"
        elif status == "skipped":
            severity = "minor"
        next_action = "continue"
        if status in {"failed", "cancelled"}:
            next_action = "stop"
        elif status == "skipped" or node_run.degraded:
            next_action = "degrade"
        return {
            "trace_id": get_trace_id(),
            "task_id": node_run.task_id,
            "stage": node_run.node_id,
            "status": status,
            "severity": severity,
            "attempt": int(runtime.get("retry_count") or 0) + 1,
            "max_attempts": int(getattr(settings, "llm_max_retries", 1) or 1) + 1,
            "latency_ms": int((node_run.elapsed_seconds or 0) * 1000),
            "model_route": {
                "provider": runtime.get("provider"),
                "model": runtime.get("model") or node_run.model_used,
                "fallback_used": bool(runtime.get("fallback_used")),
            },
            "error": {
                "code": runtime.get("error_class"),
                "message": runtime.get("error_message") or node_run.error_message,
                "retry_after_ms": 0,
            },
            "next_action": next_action,
        }

    def _extract_node_stage_envelope(self, node_run: TaskNodeRunModel) -> dict[str, Any] | None:
        if not isinstance(node_run.output_data, dict):
            return None
        envelope = node_run.output_data.get("stage_envelope")
        return dict(envelope) if isinstance(envelope, dict) else None

    def _inject_execution_meta(
        self,
        *,
        result_data: dict[str, Any],
        stage_envelopes: list[dict[str, Any]],
        degraded: bool,
        review_only: bool,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        payload = dict(result_data or {})
        execution_meta = payload.get("execution_meta")
        execution_meta = dict(execution_meta) if isinstance(execution_meta, dict) else {}
        stages = [dict(item) for item in stage_envelopes]
        stages.append(
            {
                "trace_id": get_trace_id(),
                "task_id": task_id,
                "stage": "terminal_publishability",
                "status": "degraded" if review_only else "ok",
                "severity": "major" if review_only else "none",
                "attempt": 1,
                "max_attempts": 1,
                "model_route": {"provider": None, "model": None, "fallback_used": False},
                "error": {"code": None, "message": None, "retry_after_ms": 0},
                "next_action": "stop" if review_only else "continue",
            }
        )
        execution_meta["stages"] = stages
        execution_meta["single_gate_mode"] = True
        execution_meta["degraded"] = degraded
        execution_meta["publishability"] = "review_only" if review_only else "publishable"
        payload["execution_meta"] = execution_meta
        return payload

    def _result_error_message(self, result: AgentResult) -> str:
        if not result.error:
            return "unknown agent failure"
        return str(result.error.get("message") or "unknown agent failure")

    def _extract_explicit_input_payload(self, input_data: dict[str, Any]) -> dict[str, Any]:
        explicit_keys = (
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
        payload: dict[str, Any] = {}
        for key in explicit_keys:
            value = input_data.get(key)
            if value is not None:
                payload[key] = value
        return payload

    def _summarize_output(self, output: dict | None) -> str:
        if not output:
            return ""
        keys = list(output.keys())
        if len(keys) <= 3:
            return f"keys: {', '.join(keys)}"
        return f"keys: {', '.join(keys[:3])}... ({len(keys)} total)"

    def _provider_hint(self) -> str:
        model_name = settings.llm_model_name.strip()
        if "/" in model_name:
            return model_name.split("/", 1)[0]
        return "dashscope"

    def _model_hint(self) -> str:
        model_name = settings.llm_model_name.strip()
        if "/" in model_name:
            return model_name
        return f"{self._provider_hint()}/{model_name}"

    def _provider_hint_for_node(self, node_def: dict[str, Any]) -> str:
        if node_def.get("executor") == "service":
            return "service"
        return self._provider_hint()

    def _provider_hint_from_model_used(self, model_used: str | None) -> str:
        if not model_used:
            return self._provider_hint()
        if model_used.startswith("service:"):
            return "service"
        if "/" in model_used:
            return model_used.split("/", 1)[0]
        return self._provider_hint()

    def _model_used_for_node(self, node_def: dict[str, Any]) -> str:
        if node_def.get("executor") == "service":
            return f"service:{node_def.get('service') or node_def['agent_id']}"
        return self._model_hint()


orchestrator_engine = OrchestratorEngine()
