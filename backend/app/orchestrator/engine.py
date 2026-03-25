"""Orchestrator engine: loads workflow, schedules agents sequentially, manages workspace.

Per NOTICE.md section 7:
- Agent order controlled by Orchestrator
- Agents must not skip or add steps on their own
- Single node failure must have clear error output
- Must record node execution logs
- Must support task-level tracing
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent, AgentResult
from app.agents.registry import agent_registry
from app.core.exceptions import AgentTimeoutError, AgentExecutionError
from app.core.logger import get_logger
from app.core.config import settings
from app.core.tracer import get_trace_id
from app.models.tables import TaskModel, TaskNodeRunModel, AgentModel
from app.orchestrator.workspace import Workspace
from app.orchestrator.broadcaster import broadcaster

logger = get_logger(__name__)


# Default workflow node definitions for MVP (linear chain)
DEFAULT_WORKFLOW_NODES = [
    {
        "node_id": "profile_parsing",
        "agent_id": "profile_agent",
        "name": "账号定位解析",
        "input_mapping": {"positioning": "input.positioning"},
        "output_key": "profile",
        "required": True,
    },
    {
        "node_id": "hot_topic_analysis",
        "agent_id": "hot_topic_agent",
        "name": "热点分析",
        "input_mapping": {"profile": "profile"},
        "output_key": "hot_topics",
        "required": True,
    },
    {
        "node_id": "topic_planning",
        "agent_id": "topic_planner_agent",
        "name": "选题策划",
        "input_mapping": {"profile": "profile", "hot_topics": "hot_topics"},
        "output_key": "topics",
        "required": True,
    },
    {
        "node_id": "title_generation",
        "agent_id": "title_generator_agent",
        "name": "标题生成",
        "input_mapping": {"profile": "profile", "topics": "topics"},
        "output_key": "titles",
        "required": True,
    },
    {
        "node_id": "content_writing",
        "agent_id": "content_writer_agent",
        "name": "正文生成",
        "input_mapping": {
            "profile": "profile",
            "topics": "topics",
            "titles": "titles",
            "hot_topics": "hot_topics",
        },
        "output_key": "content",
        "required": True,
    },
    {
        "node_id": "audit",
        "agent_id": "audit_agent",
        "name": "审核评估",
        "input_mapping": {"titles": "titles", "content": "content", "profile": "profile"},
        "output_key": "audit_result",
        "required": False,
    },
]


class OrchestratorEngine:
    """Executes a workflow by running agents sequentially."""

    async def run(self, task: TaskModel, db: AsyncSession) -> dict[str, Any]:
        """Run the full workflow for a task.

        Returns the final workspace snapshot as result_data.
        """
        trace_id = get_trace_id()
        workspace = Workspace(task_id=task.id, input_data=task.input_data or {})
        nodes = DEFAULT_WORKFLOW_NODES
        total_tokens = 0

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        db.add(task)
        await db.flush()

        for idx, node_def in enumerate(nodes):
            node_id = node_def["node_id"]
            agent_id = node_def["agent_id"]
            node_name = node_def["name"]
            required = node_def.get("required", True)

            # Create node run record
            node_run = TaskNodeRunModel(
                task_id=task.id,
                node_id=node_id,
                agent_id=agent_id,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(node_run)
            await db.flush()

            # Broadcast node_start
            await broadcaster.broadcast(task.id, "node_start", {
                "node_id": node_id,
                "agent_id": agent_id,
                "name": node_name,
                "index": idx,
                "total": len(nodes),
                "started_at": node_run.started_at.isoformat() if node_run.started_at else None,
            })

            # Extract input from workspace
            agent_input = workspace.extract_for_agent(node_def["input_mapping"])

            try:
                agent = agent_registry.get(agent_id)

                # Resolve effective system prompt (DB custom > default)
                effective_prompt = await self._resolve_system_prompt(
                    agent_id, agent.default_system_prompt, db
                )
                context = workspace.snapshot()
                context["system_prompt"] = effective_prompt

                result = await self._execute_agent_with_timeout(agent, agent_input, context, trace_id)

                if result.is_success:
                    workspace.set(node_def["output_key"], result.data)
                    node_run.status = "completed"
                    node_run.output_data = result.data
                else:
                    # Agent returned failure - try fallback
                    fallback_result = await agent.fallback(
                        AgentExecutionError(agent_id, result.error.get("message", "unknown") if result.error else "unknown"),
                        agent_input,
                    )
                    if fallback_result and fallback_result.is_success:
                        workspace.set(node_def["output_key"], fallback_result.data)
                        node_run.status = "completed"
                        node_run.output_data = fallback_result.data
                        node_run.degraded = True
                    elif required:
                        node_run.status = "failed"
                        node_run.error_message = result.error.get("message", "unknown") if result.error else "unknown"
                        await self._finalize_node(node_run, db)
                        await broadcaster.broadcast(task.id, "node_error", {
                            "node_id": node_id, "error": node_run.error_message,
                        })
                        raise AgentExecutionError(agent_id, node_run.error_message or "")
                    else:
                        node_run.status = "failed"
                        node_run.error_message = result.error.get("message", "unknown") if result.error else "unknown"

            except AgentExecutionError:
                raise
            except asyncio.TimeoutError:
                node_run.status = "failed"
                node_run.error_message = f"agent {agent_id} timed out"
                await self._finalize_node(node_run, db)
                await broadcaster.broadcast(task.id, "node_error", {
                    "node_id": node_id, "error": node_run.error_message,
                })
                if required:
                    raise AgentTimeoutError(agent_id)
            except Exception as e:
                logger.error("node_execution_error", task_id=task.id, node_id=node_id, error=str(e))
                node_run.status = "failed"
                node_run.error_message = str(e)
                await self._finalize_node(node_run, db)
                await broadcaster.broadcast(task.id, "node_error", {
                    "node_id": node_id, "error": str(e),
                })
                if required:
                    raise AgentExecutionError(agent_id, str(e))

            await self._finalize_node(node_run, db)

            # Broadcast node_complete
            if node_run.status == "completed":
                await broadcaster.broadcast(task.id, "node_complete", {
                    "node_id": node_id,
                    "agent_id": agent_id,
                    "name": node_name,
                    "elapsed_seconds": node_run.elapsed_seconds,
                    "degraded": node_run.degraded,
                    "output_summary": self._summarize_output(node_run.output_data),
                })

            # Accumulate tokens
            if node_run.prompt_tokens:
                total_tokens += node_run.prompt_tokens
            if node_run.completion_tokens:
                total_tokens += node_run.completion_tokens

        # Task completed
        result_data = workspace.snapshot()
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        task.result_data = result_data
        task.total_tokens = total_tokens
        if task.started_at:
            task.elapsed_seconds = (task.completed_at - task.started_at).total_seconds()
        db.add(task)
        await db.flush()

        await broadcaster.broadcast(task.id, "task_complete", {
            "task_id": task.id,
            "elapsed_seconds": task.elapsed_seconds,
        })
        await broadcaster.close_task(task.id)

        return result_data

    async def _execute_agent_with_timeout(
        self, agent: BaseAgent, input_data: dict, context: dict, trace_id: str
    ) -> AgentResult:
        """Execute an agent with a timeout."""
        return await asyncio.wait_for(
            agent.execute(input_data, context),
            timeout=settings.agent_timeout,
        )

    async def _resolve_system_prompt(
        self, agent_id: str, default_prompt: str, db: AsyncSession
    ) -> str:
        """Resolve the effective system prompt for an agent.

        Priority: DB custom prompt > agent default prompt.
        """
        from sqlalchemy import select

        stmt = select(AgentModel.prompt_template).where(AgentModel.agent_id == agent_id)
        result = await db.execute(stmt)
        db_prompt = result.scalar_one_or_none()

        if db_prompt:
            logger.info("prompt_resolved", agent_id=agent_id, source="custom")
            return db_prompt

        logger.info("prompt_resolved", agent_id=agent_id, source="default")
        return default_prompt

    async def _finalize_node(self, node_run: TaskNodeRunModel, db: AsyncSession) -> None:
        """Compute elapsed time and persist node run."""
        node_run.completed_at = datetime.now(timezone.utc)
        if node_run.started_at and node_run.completed_at:
            node_run.elapsed_seconds = (node_run.completed_at - node_run.started_at).total_seconds()
        db.add(node_run)
        await db.flush()

    def _summarize_output(self, output: dict | None) -> str:
        """Create a brief text summary of the output for SSE display."""
        if not output:
            return ""
        keys = list(output.keys())
        if len(keys) <= 3:
            return f"keys: {', '.join(keys)}"
        return f"keys: {', '.join(keys[:3])}... ({len(keys)} total)"


# Singleton
orchestrator_engine = OrchestratorEngine()
