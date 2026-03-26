# -*- coding: utf-8 -*-
"""
DeskClaw 发布端
负责接收用户需求，创建结构化任务，写入任务文件
"""

import logging
import re
from typing import Optional, List
from pathlib import Path

from models import Task, Constraints, TaskStatus, EventSource, EventLog, asdict
from storage import TaskStorage, StorageError

logger = logging.getLogger(__name__)


class TaskDecomposer:
    """任务分解器 - 将自然语言需求拆解为步骤"""

    # 常见的编程相关关键词
    CODE_KEYWORDS = [
        "修改", "添加", "删除", "创建", "实现", "修复", "更新",
        "代码", "函数", "类", "模块", "文件", "接口", "API",
        "测试", "部署", "构建", "编译", "运行", "调试"
    ]

    @classmethod
    def decompose(cls, user_request: str) -> List[str]:
        """
        将用户需求分解为可执行步骤

        Args:
            user_request: 用户原始需求

        Returns:
            步骤列表
        """
        steps = []

        # 检测是否包含多个请求（用换行、分号或数字分隔）
        lines = re.split(r'[\n;]|(?=\d+\.)', user_request)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 去除序号
            line = re.sub(r'^\d+[.)、]\s*', '', line)

            if line and len(line) > 5:
                steps.append(line)

        # 如果没有成功分解，创建一个默认步骤
        if not steps:
            steps = [f"执行任务: {user_request[:50]}"]

        return steps

    @classmethod
    def extract_constraints(cls, user_request: str) -> Constraints:
        """
        从需求中提取约束条件

        Args:
            user_request: 用户原始需求

        Returns:
            约束条件对象
        """
        must_do = []
        must_not = []

        # 检测 must not 约束
        not_patterns = [
            r'不要\s*(.+)',
            r'禁止\s*(.+)',
            r'不要修改\s*(.+)',
            r'保持\s*(.+)',
        ]

        for pattern in not_patterns:
            matches = re.findall(pattern, user_request)
            must_not.extend(matches)

        # 检测 must do 约束
        do_patterns = [
            r'必须\s*(.+)',
            r'一定要\s*(.+)',
            r'需要先\s*(.+)',
        ]

        for pattern in do_patterns:
            matches = re.findall(pattern, user_request)
            must_do.extend(matches)

        return Constraints(must_do=must_do, must_not=must_not)


class DeskClawPublisher:
    """DeskClaw 发布端 - 创建和管理任务"""

    def __init__(self, tasks_dir: str = "bridge/tasks"):
        """
        初始化发布端

        Args:
            tasks_dir: 任务文件目录
        """
        self.storage = TaskStorage(tasks_dir)

    def create_task(
        self,
        user_request: str,
        project: str = "",
        title: str = "",
        custom_decomposition: List[str] = None,
        custom_constraints: Constraints = None,
    ) -> Task:
        """
        创建新任务

        Args:
            user_request: 用户原始需求
            project: 项目名称
            title: 任务标题（不提供则自动生成）
            custom_decomposition: 自定义分解步骤
            custom_constraints: 自定义约束

        Returns:
            创建的任务对象
        """
        # 自动生成标题
        if not title:
            # 取需求的前50个字符作为标题
            title = user_request[:50].strip()
            if len(user_request) > 50:
                title += "..."

        # 分解任务
        decomposition = custom_decomposition or TaskDecomposer.decompose(user_request)

        # 提取约束
        constraints = custom_constraints or TaskDecomposer.extract_constraints(user_request)

        # 创建任务
        task = Task.create_new(
            title=title,
            user_request=user_request,
            project=project,
            decomposition=decomposition,
            constraints=constraints
        )

        # 保存到文件
        self.storage.save_task(task)

        logger.info(f"任务已创建: {task.task_id} - {task.title}")
        return task

    def cancel_task(self, task_id: str, reason: str = "") -> Optional[Task]:
        """
        取消任务

        Args:
            task_id: 任务ID
            reason: 取消原因

        Returns:
            更新后的任务
        """
        message = f"任务已取消: {reason}" if reason else "任务已取消"
        return self.storage.update_task_status(
            task_id,
            TaskStatus.CANCELLED,
            EventSource.DESKCLAW,
            message
        )

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务详情"""
        return self.storage.load_task(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """列出任务"""
        return self.storage.list_tasks(status)

    def update_task(
        self,
        task_id: str,
        title: str = None,
        user_request: str = None,
        decomposition: List[str] = None,
    ) -> Optional[Task]:
        """
        更新任务（只更新 DeskClaw 负责的字段）

        Args:
            task_id: 任务ID
            title: 新标题
            user_request: 新需求
            decomposition: 新分解步骤

        Returns:
            更新后的任务
        """
        task = self.storage.load_task(task_id)
        if task is None:
            return None

        # 检查任务状态，只有 queued/cancelled 才能更新
        if task.status not in [TaskStatus.QUEUED.value, TaskStatus.CANCELLED.value]:
            logger.warning(f"任务 {task_id} 状态为 {task.status}，不允许更新")
            return None

        if title is not None:
            task.title = title
        if user_request is not None:
            task.user_request = user_request
        if decomposition is not None:
            task.decomposition = decomposition

        self.storage.save_task(task)
        return task

    def add_constraint(
        self,
        task_id: str,
        constraint_type: str,  # "must_do" 或 "must_not"
        value: str
    ) -> Optional[Task]:
        """
        添加约束条件

        Args:
            task_id: 任务ID
            constraint_type: 约束类型
            value: 约束值
        """
        task = self.storage.load_task(task_id)
        if task is None:
            return None

        if constraint_type == "must_do":
            task.constraints.must_do.append(value)
        elif constraint_type == "must_not":
            task.constraints.must_not.append(value)

        self.storage.save_task(task)
        return task


# 便捷函数
def publish_task(
    user_request: str,
    project: str = "",
    tasks_dir: str = "bridge/tasks"
) -> Task:
    """
    便捷函数：发布一个任务

    Args:
        user_request: 用户需求
        project: 项目名称
        tasks_dir: 任务目录

    Returns:
        创建的任务
    """
    publisher = DeskClawPublisher(tasks_dir)
    return publisher.create_task(user_request, project)
