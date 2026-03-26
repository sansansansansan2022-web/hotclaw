# -*- coding: utf-8 -*-
"""
任务数据模型定义
DeskClaw 与 Qoder 协作桥接 - 数据结构
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class TaskStatus(str, Enum):
    """任务状态枚举"""
    QUEUED = "queued"           # 待执行
    CLAIMED = "claimed"         # 已认领
    RUNNING = "running"         # 执行中
    SUCCESS = "success"         # 执行成功
    FAILED = "failed"           # 执行失败
    CANCELLED = "cancelled"     # 已取消


class EventSource(str, Enum):
    """事件来源枚举"""
    DESKCLAW = "deskclaw"
    QODER = "qoder"
    REPORTER = "reporter"


# 有效的状态流转
VALID_TRANSITIONS = {
    TaskStatus.QUEUED: [TaskStatus.CLAIMED, TaskStatus.CANCELLED],
    TaskStatus.CLAIMED: [TaskStatus.RUNNING, TaskStatus.CANCELLED],
    TaskStatus.RUNNING: [TaskStatus.SUCCESS, TaskStatus.FAILED],
    TaskStatus.SUCCESS: [],
    TaskStatus.FAILED: [],
    TaskStatus.CANCELLED: [],
}


@dataclass
class EventLog:
    """事件日志条目"""
    ts: str                           # ISO8601 时间戳
    by: str                           # 事件来源 (deskclaw/qoder/reporter)
    event: str                        # 事件类型
    message: str                      # 事件消息

    @classmethod
    def create(cls, source: EventSource, event: str, message: str) -> "EventLog":
        """创建新事件日志"""
        return cls(
            ts=datetime.now(timezone.utc).isoformat(),
            by=source.value,
            event=event,
            message=message
        )


@dataclass
class ExecutionResult:
    """执行结果数据"""
    claimed_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    current_step: str = ""
    changed_files: list = field(default_factory=list)
    test_results: list = field(default_factory=list)
    result_summary: str = ""
    error_message: str = ""
    next_action: str = ""


@dataclass
class ReportState:
    """汇报状态（用于去重）"""
    last_reported_event_index: int = 0
    last_reported_version: int = 1


@dataclass
class Constraints:
    """任务约束条件"""
    must_do: list = field(default_factory=list)
    must_not: list = field(default_factory=list)


@dataclass
class Task:
    """完整任务数据模型"""
    task_id: str
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    source: str = "deskclaw"
    project: str = ""
    title: str = ""
    user_request: str = ""
    decomposition: list = field(default_factory=list)
    constraints: Constraints = field(default_factory=Constraints)
    status: str = TaskStatus.QUEUED.value
    executor: str = "qoder"
    execution: ExecutionResult = field(default_factory=ExecutionResult)
    event_logs: list = field(default_factory=list)
    report_state: ReportState = field(default_factory=ReportState)

    def __post_init__(self):
        """初始化默认值"""
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    @classmethod
    def create_new(
        cls,
        title: str,
        user_request: str,
        project: str = "",
        decomposition: list = None,
        constraints: Constraints = None
    ) -> "Task":
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        event_log = EventLog.create(
            EventSource.DESKCLAW,
            "task_created",
            f"任务已创建: {title}"
        )
        return cls(
            task_id=task_id,
            title=title,
            user_request=user_request,
            project=project,
            decomposition=decomposition or [],
            constraints=constraints or Constraints(),
            event_logs=[asdict(event_log)],
        )

    def can_transition_to(self, new_status: TaskStatus) -> bool:
        """检查状态流转是否合法"""
        current = TaskStatus(self.status)
        return new_status in VALID_TRANSITIONS.get(current, [])

    def transition_to(self, new_status: TaskStatus, source: EventSource, message: str = "") -> bool:
        """执行状态流转"""
        if not self.can_transition_to(new_status):
            return False

        self.status = new_status.value
        self.version += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()

        event_log = EventLog.create(source, f"status_{new_status.value}", message)
        self.event_logs.append(asdict(event_log))

        return True

    def to_dict(self) -> dict:
        """转换为字典"""
        result = asdict(self)
        # 将嵌套对象转换回普通结构
        result["constraints"] = asdict(self.constraints) if isinstance(self.constraints, Constraints) else self.constraints
        result["execution"] = asdict(self.execution) if isinstance(self.execution, ExecutionResult) else self.execution
        result["report_state"] = asdict(self.report_state) if isinstance(self.report_state, ReportState) else self.report_state
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """从字典创建任务"""
        # 重建嵌套对象
        if "constraints" in data and isinstance(data["constraints"], dict):
            data["constraints"] = Constraints(**data["constraints"])
        if "execution" in data and isinstance(data["execution"], dict):
            data["execution"] = ExecutionResult(**data["execution"])
        if "report_state" in data and isinstance(data["report_state"], dict):
            data["report_state"] = ReportState(**data["report_state"])
        return cls(**data)


def generate_progress_report(task: Task) -> str:
    """生成给用户看的中文进度汇报"""
    status_labels = {
        TaskStatus.QUEUED.value: "待执行",
        TaskStatus.CLAIMED.value: "已认领",
        TaskStatus.RUNNING.value: "执行中",
        TaskStatus.SUCCESS.value: "已完成",
        TaskStatus.FAILED.value: "执行失败",
        TaskStatus.CANCELLED.value: "已取消",
    }

    parts = []

    # 状态概览
    status_label = status_labels.get(task.status, task.status)
    parts.append(f"[{task.title}] {status_label}")

    # 当前步骤
    if task.execution.current_step:
        parts.append(f"当前: {task.execution.current_step}")

    # 文件变更
    if task.execution.changed_files:
        count = len(task.execution.changed_files)
        parts.append(f"已修改 {count} 个文件")

    # 测试结果
    if task.execution.test_results:
        passed = sum(1 for r in task.execution.test_results if r.get("passed"))
        total = len(task.execution.test_results)
        parts.append(f"测试: {passed}/{total} 通过")

    # 结果摘要
    if task.execution.result_summary:
        parts.append(f"结果: {task.execution.result_summary}")

    # 错误信息
    if task.execution.error_message:
        parts.append(f"错误: {task.execution.error_message}")

    return " | ".join(parts) if parts else f"[{task.title}] 状态: {status_label}"
