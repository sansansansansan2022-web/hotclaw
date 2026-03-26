# -*- coding: utf-8 -*-
"""
DeskClaw-Qoder 协作桥接工具
DeskClaw 作为需求编排助理，Qoder 作为代码执行代理，
通过结构化 JSON 任务文件进行协作。
"""

from models import Task, TaskStatus, EventSource, EventLog, Constraints, ExecutionResult
from storage import TaskStorage, StorageError
from deskclaw_publisher import DeskClawPublisher, TaskDecomposer
from qoder_worker import QoderWorker, TaskExecutor
from reporter import TaskReporter, create_console_reporter

__version__ = "1.0.0"

__all__ = [
    "Task",
    "TaskStatus",
    "EventSource",
    "EventLog",
    "Constraints",
    "ExecutionResult",
    "TaskStorage",
    "StorageError",
    "DeskClawPublisher",
    "TaskDecomposer",
    "QoderWorker",
    "TaskExecutor",
    "TaskReporter",
    "create_console_reporter",
]
