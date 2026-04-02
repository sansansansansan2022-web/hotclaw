"""
Workspace: isolated context container for a single task execution.

【工作空间】
每个任务创建一个独立的 Workspace，用于在智能体之间共享数据。
是"数据传递"的核心载体。

设计思想：
- 任务间隔离：每个任务有独立的 Workspace，互不干扰
- 智能体按需读取：input_mapping 定义"需要什么" → "从哪取"
- 数据持久化：snapshot() 导出完整数据存入数据库

面试点：
- 数据共享模式（vs 全局变量）
- 字典的动态属性访问
- Pipeline 数据依赖管理
"""

from typing import Any
from app.core.logger import get_logger

logger = get_logger(__name__)


class Workspace:
    """
    Task-scoped context container for agent data sharing.

    【工作空间】
    封装任务执行过程中的所有中间数据。

    数据结构：
        {
            "input": { ... },       # 用户原始输入（positioning）
            "profile": { ... },     # 账号画像
            "hot_topics": { ... },  # 热点分析结果
            "topics": [...],        # 选题列表
            "titles": [...],        # 候选标题
            "content": { ... },     # 文章正文
            "audit_result": { ... } # 审核结果
        }

    使用方式：
        ws = Workspace(task_id="xxx", input_data={"positioning": "..."})

        # 节点 1 执行后存入结果
        ws.set("profile", {"domain": "科技", "target_audience": "..."})

        # 节点 2 提取需要的输入
        agent_input = ws.extract_for_agent({"profile": "profile"})
        # → {"profile": {"domain": "科技", "target_audience": "..."}}
    """

    def __init__(self, task_id: str, input_data: dict) -> None:
        """
        Args:
            task_id: 任务 ID（用于日志追踪）
            input_data: 用户输入数据，通常包含 positioning
        """
        self.task_id = task_id
        # _data 是内部存储，所有智能体的输入输出都存在这里
        self._data: dict[str, Any] = {"input": input_data}

    def get(self, key: str) -> Any:
        """
        Get a value from the workspace by key.

        Args:
            key: 数据 key，如 "profile"、"hot_topics"

        Returns:
            存储的值，不存在返回 None
        """
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the workspace.

        智能体执行完成后调用，将结果存入 Workspace，
        供后续智能体作为输入使用。

        Args:
            key: 数据 key
            value: 要存储的值（通常是字典或列表）
        """
        self._data[key] = value
        logger.info("workspace_set", task_id=self.task_id, key=key)

    def get_input(self) -> dict:
        """Get the original task input (positioning text)."""
        return self._data.get("input", {})

    def snapshot(self) -> dict:
        """
        Return a snapshot of all workspace data.

        【快照】用于持久化到数据库
        将 Workspace 中所有数据复制一份字典返回，
        存入 TaskModel.result_data 字段。

        为什么复制？避免后续修改影响已存储的结果。
        """
        return dict(self._data)

    def extract_for_agent(self, input_mapping: dict[str, str]) -> dict:
        """
        Extract agent input from workspace using a flat key mapping.

        【智能体输入提取】
        根据 input_mapping 从 Workspace 中提取本智能体需要的数据。

        input_mapping 格式：
            { "agent_input_field": "workspace_key" }

        支持两种 workspace_key 格式：
        1. 简单 key：如 "profile" → workspace["profile"]
        2. 输入引用：如 "input.positioning" → workspace["input"]["positioning"]

        Example:
            input_mapping = {"profile": "profile", "hot_topics": "hot_topics"}
            # → {"profile": {...}, "hot_topics": {...}}

            input_mapping = {"positioning": "input.positioning"}
            # → {"positioning": "专注职场成长的公众号..."}

        Args:
            input_mapping: 智能体需要的输入字段映射

        Returns:
            提取后的输入字典，直接传给智能体的 execute() 方法
        """
        result: dict[str, Any] = {}
        for field_name, workspace_key in input_mapping.items():
            if workspace_key.startswith("input."):
                # 【输入引用】从原始输入中提取（如用户写的 positioning 文本）
                inner_key = workspace_key[len("input."):]
                result[field_name] = self._data.get("input", {}).get(inner_key)
            else:
                # 【常规引用】从 Workspace 数据中提取
                result[field_name] = self._data.get(workspace_key)
        return result
