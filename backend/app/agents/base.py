"""
Base class for all agents.

【智能体基类】
所有业务智能体的抽象基类，定义智能体的标准接口。

核心设计原则（来自 NOTICE.md）：
- 智能体是工作流节点，负责单一业务任务
- 有清晰的输入/输出定义
- 返回结构化 JSON 数据
- 可以调用技能（Skills）
- 单一职责，不应有多重职责

面试点：
- ABC 抽象基类 + abstractmethod
- AgentResult 统一返回格式
- Fallback 降级策略
- Template Method Pattern（模板方法模式）
"""

from abc import ABC, abstractmethod
from typing import Any
from app.core.logger import get_logger

logger = get_logger(__name__)


class AgentResult:
    """
    Standardized agent result per NOTICE.md section 8.2.

    【智能体执行结果】
    所有智能体必须返回 AgentResult，实现统一的成功/失败处理。

    Attributes:
        status: 结果状态 ("success" | "failed")
        agent_name: 智能体 ID（用于日志追踪）
        data: 成功时的结构化输出数据
        error: 失败时的错误信息
        trace_id: 追踪 ID（用于日志关联）
    """

    def __init__(
        self,
        status: str,
        agent_name: str,
        data: dict | None = None,
        error: dict | None = None,
        trace_id: str = "",
    ):
        self.status = status       # "success" 或 "failed"
        self.agent_name = agent_name
        self.data = data           # 结构化输出（供后续节点使用）
        self.error = error        # 错误信息 {code, message}
        self.trace_id = trace_id   # 追踪 ID

    def to_dict(self) -> dict:
        """转换为字典，用于日志和序列化。"""
        return {
            "status": self.status,
            "agent_name": self.agent_name,
            "data": self.data,
            "error": self.error,
            "trace_id": self.trace_id,
        }

    @property
    def is_success(self) -> bool:
        """判断是否成功执行。"""
        return self.status == "success"


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    【智能体抽象基类】
    所有具体智能体（ProfileAgent、HotTopicAgent 等）都继承此类。

    子类必须实现：
    - agent_id: 唯一标识（如 "profile_agent"）
    - name: 中文显示名称
    - description: 职能描述
    - default_system_prompt: 默认系统提示词
    - execute(): 核心执行逻辑

    可选重写：
    - fallback(): 降级策略（默认返回 None，即不降级）
    """

    # 类属性：子类必须定义
    agent_id: str = ""      # 智能体唯一 ID
    name: str = ""          # 中文名称
    description: str = ""   # 职能说明
    default_system_prompt: str = ""  # 默认系统提示词

    def __init__(self, config: dict | None = None):
        """
        Args:
            config: 可选的配置字典（从数据库加载的自定义配置）
        """
        self.config = config or {}

    def get_system_prompt(self, context: dict) -> str:
        """
        Get the effective system prompt from context, falling back to default.

        【Prompt 解析】
        优先级：context["system_prompt"] > default_system_prompt

        context["system_prompt"] 来自数据库自定义配置（如果存在）
        这样管理员可以在不修改代码的情况下调整智能体行为。
        """
        return context.get("system_prompt") or self.default_system_prompt

    @abstractmethod
    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """
        Execute the agent's task.

        【核心执行方法】子类必须实现

        工作流程：
        1. 解析输入（从 input_data 提取需要的字段）
        2. 构建 Prompt（合并 system_prompt + user_input）
        3. 调用 LLM 获取结果
        4. 解析 LLM 输出为结构化 JSON
        5. 返回 AgentResult

        Args:
            input_data: 本智能体需要的输入数据（由 Workspace.extract_for_agent() 构建）
            context: 工作空间上下文（包含 system_prompt 和前置节点输出）

        Returns:
            AgentResult: 包含 status/data/error
        """
        ...

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """
        Fallback strategy when execution fails.

        【降级策略】
        当 execute() 抛出异常或返回失败结果时，编排引擎会调用此方法。

        默认返回 None（不降级，直接失败）。
        子类可重写实现降级逻辑，如：
        - 使用更简单的 Prompt 重试
        - 返回预设的默认数据
        - 切换到备用模型

        Args:
            error: 抛出的异常对象
            input_data: 原始输入数据

        Returns:
            降级后的结果，None 表示不降级
        """
        return None

    # ========== 辅助方法 ==========

    def _success(self, data: dict, trace_id: str = "") -> AgentResult:
        """
        构建成功结果。

        使用示例：
            return self._success({"domain": "科技", "target_audience": "年轻人"})
        """
        return AgentResult(
            status="success",
            agent_name=self.agent_id,
            data=data,
            trace_id=trace_id,
        )

    def _failure(self, code: str, message: str, trace_id: str = "") -> AgentResult:
        """
        构建失败结果。

        使用示例：
            return self._failure("LLM_PARSE_ERROR", "无法解析 JSON 输出")
        """
        return AgentResult(
            status="failed",
            agent_name=self.agent_id,
            error={"code": code, "message": message},
            trace_id=trace_id,
        )
