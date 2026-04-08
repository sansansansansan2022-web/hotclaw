"""
Orchestrator engine: loads workflow, schedules agents sequentially, manages workspace.

【编排引擎】
这是整个系统的"大脑"，负责：
1. 定义工作流的节点顺序（DEFAULT_WORKFLOW_NODES）
2. 按顺序执行每个智能体
3. 管理 Workspace 数据共享
4. 通过 SSE 广播实时状态
5. 处理超时和降级策略

核心设计原则（来自 NOTICE.md）：
- 智能体顺序由编排器控制，智能体不能自行跳过或添加步骤
- 单节点失败必须有明确的错误输出
- 必须记录节点执行日志
- 必须支持任务级追踪

面试点：
- Pipeline Pattern（线性流水线）
- asyncio.wait_for 超时控制
- Fallback 降级策略
- Workspace 数据传递模式
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
from app.services.account_service import account_service

logger = get_logger(__name__)


# =============================================================================
# 工作流节点定义
# =============================================================================

# Default workflow node definitions for MVP (linear chain)
# 【工作流定义】定义 6 个智能体的执行顺序和依赖关系
# 每个节点包含：
#   - node_id: 唯一标识
#   - agent_id: 对应的智能体 ID（用于注册表查找）
#   - name: 中文显示名称
#   - input_mapping: 从 Workspace 提取哪些数据作为输入
#   - output_key: 输出存到 Workspace 的哪个 key
#   - required: 是否必须成功（False 时失败不中断流水线）

DEFAULT_WORKFLOW_NODES = [
    # ========== 节点 1: 账号定位解析 ==========
    {
        "node_id": "profile_parsing",
        "agent_id": "profile_agent",
        "name": "账号定位解析",
        # 【输入映射】从用户输入的 positioning 提取
        "input_mapping": {"positioning": "input.positioning"},
        # 【输出】账号画像存到 workspace["profile"]
        "output_key": "profile",
        # 账号解析是后续所有节点的基础，必须成功
        "required": True,
    },
    # ========== 节点 2: 热点分析 ==========
    {
        "node_id": "hot_topic_analysis",
        "agent_id": "hot_topic_agent",
        "name": "热点分析",
        # 依赖账号画像来搜索相关热点
        "input_mapping": {"profile": "profile"},
        "output_key": "hot_topics",
        "required": True,
    },
    # ========== 节点 3: 选题策划 ==========
    {
        "node_id": "topic_planning",
        "agent_id": "topic_planner_agent",
        "name": "选题策划",
        # 需要画像和热点两个输入
        "input_mapping": {"profile": "profile", "hot_topics": "hot_topics"},
        "output_key": "topics",
        "required": True,
    },
    # ========== 节点 4: 标题生成 ==========
    {
        "node_id": "title_generation",
        "agent_id": "title_generator_agent",
        "name": "标题生成",
        # 基于画像和选题生成标题
        "input_mapping": {"profile": "profile", "topics": "topics"},
        "output_key": "titles",
        "required": True,
    },
    # ========== 节点 5: 正文生成 ==========
    {
        "node_id": "content_writing",
        "agent_id": "content_writer_agent",
        "name": "正文生成",
        # 正文需要所有前置信息
        "input_mapping": {
            "profile": "profile",
            "topics": "topics",
            "titles": "titles",
            "hot_topics": "hot_topics",
        },
        "output_key": "content",
        "required": True,
    },
    # ========== 节点 6: 审核评估 ==========
    {
        "node_id": "audit",
        "agent_id": "audit_agent",
        "name": "审核评估",
        # 审核需要标题和正文
        "input_mapping": {"titles": "titles", "content": "content", "profile": "profile"},
        "output_key": "audit_result",
        # 【关键】审核不是必需的，文章生成后可直接返回
        "required": False,
    },
]


class OrchestratorEngine:
    """
    执行工作流的引擎。

    【核心职责】
    1. 遍历工作流节点，按顺序执行
    2. 为每个节点创建运行记录 (TaskNodeRunModel)
    3. 从 Workspace 提取智能体需要的输入数据
    4. 执行智能体，处理超时和异常
    5. 管理降级策略（Fallback）
    6. 通过 SSE 广播实时状态
    """

    async def run(self, task: TaskModel, db: AsyncSession) -> dict[str, Any]:
        """
        执行完整的工作流。

        Args:
            task: 任务模型实例（包含 positioning 输入）
            db: 数据库会话（由调用者管理提交）

        Returns:
            最终的 workspace 快照，作为 result_data 存入数据库

        工作流程：
        1. 初始化 Workspace
        2. 遍历每个节点：
           - 创建 TaskNodeRunModel 记录
           - 广播 node_start 事件
           - 提取输入、解析 Prompt、执行智能体
           - 成功 → 存结果，广播 node_complete
           - 失败 → 尝试 Fallback，仍失败则根据 required 决定是否中断
        3. 所有节点完成，广播 task_complete
        """
        # 获取当前请求的 trace_id（用于日志关联）
        trace_id = get_trace_id()
        # 【关键】Workspace 是任务级数据容器，所有智能体共享
        workspace = Workspace(task_id=task.id, input_data=task.input_data or {})
        nodes = DEFAULT_WORKFLOW_NODES
        total_tokens = 0

        # ===== Account Context 注入 =====
        # 如果任务关联了账号，获取账号上下文并注入到 workspace
        # 这样智能体可以访问账号的定位、受众、内容策略等信息
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
                effective_mode=ops_context.get("run_strategy", {}).get("effective_mode"),
            )

        # ===== 初始化任务状态 =====
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        db.add(task)
        # flush: 立即写入数据库（但不 commit），确保其他会话能看到
        await db.flush()

        # ===== 遍历节点执行 =====
        for idx, node_def in enumerate(nodes):
            node_id = node_def["node_id"]
            agent_id = node_def["agent_id"]
            node_name = node_def["name"]
            required = node_def.get("required", True)

            # ----- 创建节点运行记录 -----
            node_run = TaskNodeRunModel(
                task_id=task.id,
                node_id=node_id,
                agent_id=agent_id,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(node_run)
            await db.flush()

            # ----- 广播节点启动事件 -----
            # 前端 EventSource 监听此事件，开始显示"执行中"状态
            await broadcaster.broadcast(task.id, "node_start", {
                "node_id": node_id,
                "agent_id": agent_id,
                "name": node_name,
                "index": idx,
                "total": len(nodes),
                "started_at": node_run.started_at.isoformat() if node_run.started_at else None,
            })

            # ----- 从 Workspace 提取输入 -----
            # input_mapping 定义了"本智能体需要什么数据" → "从 Workspace 哪里取"
            # 例如：{"profile": "profile"} → workspace.get("profile")
            agent_input = workspace.extract_for_agent(node_def["input_mapping"])

            try:
                # ----- 获取智能体实例 -----
                agent = agent_registry.get(agent_id)

                # ----- 解析系统 Prompt -----
                # 【优先级】数据库自定义 > 智能体默认
                effective_prompt = await self._resolve_system_prompt(
                    agent_id, agent.default_system_prompt, db
                )
                context = workspace.snapshot()
                context["system_prompt"] = effective_prompt

                # ----- 【核心】执行智能体（带超时）-----
                result = await self._execute_agent_with_timeout(
                    agent, agent_input, context, trace_id
                )

                # ----- 处理执行结果 -----
                if result.is_success:
                    # 成功：存入 Workspace，供后续节点使用
                    workspace.set(node_def["output_key"], result.data)
                    node_run.status = "completed"
                    node_run.output_data = result.data
                else:
                    # 失败：尝试降级策略
                    logger.warning("agent_returned_failure", agent_id=agent_id,
                                   error=result.error)
                    fallback_result = await agent.fallback(
                        AgentExecutionError(
                            agent_id,
                            result.error.get("message", "unknown") if result.error else "unknown"
                        ),
                        agent_input,
                    )
                    if fallback_result and fallback_result.is_success:
                        # 降级成功：使用 fallback 结果，标记为 degraded
                        workspace.set(node_def["output_key"], fallback_result.data)
                        node_run.status = "completed"
                        node_run.output_data = fallback_result.data
                        node_run.degraded = True  # 标记降级
                    elif required:
                        # 降级失败 + required → 中断流水线
                        node_run.status = "failed"
                        node_run.error_message = (
                            result.error.get("message", "unknown") if result.error else "unknown"
                        )
                        await self._finalize_node(node_run, db)
                        await broadcaster.broadcast(task.id, "node_error", {
                            "node_id": node_id, "error": node_run.error_message,
                        })
                        raise AgentExecutionError(agent_id, node_run.error_message or "")
                    else:
                        # 非必需节点失败 → 继续流水线，但记录错误
                        node_run.status = "failed"
                        node_run.error_message = (
                            result.error.get("message", "unknown") if result.error else "unknown"
                        )

            except AgentExecutionError:
                # AgentExecutionError 是业务异常，直接重新抛出
                raise
            except asyncio.TimeoutError:
                # 【超时处理】执行时间超过 agent_timeout
                logger.warning("agent_timeout", agent_id=agent_id, timeout=settings.agent_timeout)
                node_run.status = "failed"
                node_run.error_message = f"agent {agent_id} timed out"
                await self._finalize_node(node_run, db)
                await broadcaster.broadcast(task.id, "node_error", {
                    "node_id": node_id, "error": node_run.error_message,
                })
                if required:
                    raise AgentTimeoutError(agent_id)
            except Exception as e:
                # 【兜底异常处理】捕获所有未预期错误
                logger.error("node_execution_error", task_id=task.id, node_id=node_id, error=str(e))
                node_run.status = "failed"
                node_run.error_message = str(e)
                await self._finalize_node(node_run, db)
                await broadcaster.broadcast(task.id, "node_error", {
                    "node_id": node_id, "error": str(e),
                })
                if required:
                    raise AgentExecutionError(agent_id, str(e))

            # ----- 结束节点：计算耗时 + 持久化 -----
            await self._finalize_node(node_run, db)

            # ----- 广播节点完成事件 -----
            if node_run.status == "completed":
                await broadcaster.broadcast(task.id, "node_complete", {
                    "node_id": node_id,
                    "agent_id": agent_id,
                    "name": node_name,
                    "elapsed_seconds": node_run.elapsed_seconds,
                    "degraded": node_run.degraded,
                    "output_summary": self._summarize_output(node_run.output_data),
                })

            # 累计 Token 消耗
            if node_run.prompt_tokens:
                total_tokens += node_run.prompt_tokens
            if node_run.completion_tokens:
                total_tokens += node_run.completion_tokens

        # ===== 任务完成 =====
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
        # 通知 SSE 关闭连接，触发历史清理（60秒后）
        await broadcaster.close_task(task.id)

        return result_data

    async def _execute_agent_with_timeout(
        self, agent: BaseAgent, input_data: dict, context: dict, trace_id: str
    ) -> AgentResult:
        """
        使用超时控制执行智能体。

        【关键设计】asyncio.wait_for 实现超时
        当超时时，抛出 asyncio.TimeoutError 异常，
        由调用者捕获并决定如何处理（降级 or 中断）。
        """
        return await asyncio.wait_for(
            agent.execute(input_data, context),
            timeout=settings.agent_timeout,  # 默认 120 秒
        )

    async def _resolve_system_prompt(
        self, agent_id: str, default_prompt: str, db: AsyncSession
    ) -> str:
        """
        解析有效的系统 Prompt。

        【Prompt 优先级】数据库自定义 > 智能体默认
        允许管理员在数据库中覆盖特定智能体的 Prompt，
        实现零代码调整智能体行为。

        Args:
            agent_id: 智能体 ID
            default_prompt: 智能体代码中定义的默认 Prompt
            db: 数据库会话

        Returns:
            最终使用的系统 Prompt
        """
        from sqlalchemy import select

        # 查询数据库是否有自定义 Prompt
        stmt = select(AgentModel.prompt_template).where(AgentModel.agent_id == agent_id)
        result = await db.execute(stmt)
        db_prompt = result.scalar_one_or_none()

        if db_prompt:
            logger.info("prompt_resolved", agent_id=agent_id, source="custom")
            return db_prompt

        logger.info("prompt_resolved", agent_id=agent_id, source="default")
        return default_prompt

    async def _finalize_node(self, node_run: TaskNodeRunModel, db: AsyncSession) -> None:
        """
        结束节点：计算耗时并持久化。

        注意：只 flush 不 commit，事务由调用者（run 方法）统一管理。
        """
        node_run.completed_at = datetime.now(timezone.utc)
        if node_run.started_at and node_run.completed_at:
            # 计算执行耗时（秒）
            node_run.elapsed_seconds = (node_run.completed_at - node_run.started_at).total_seconds()
        db.add(node_run)
        await db.flush()

    def _summarize_output(self, output: dict | None) -> str:
        """
        为 SSE 输出创建简短摘要。

        前端只需要知道输出了哪些字段，不需要完整数据。
        例如：'keys: domain, subdomain, target_audience... (7 total)'
        """
        if not output:
            return ""
        keys = list(output.keys())
        if len(keys) <= 3:
            return f"keys: {', '.join(keys)}"
        return f"keys: {', '.join(keys[:3])}... ({len(keys)} total)"


# 【单例模式】全局编排引擎实例
# 整个应用共享同一个引擎实例
orchestrator_engine = OrchestratorEngine()
