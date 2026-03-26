# -*- coding: utf-8 -*-
"""
Qoder 执行端
负责轮询任务文件、认领任务、执行代码、汇报结果
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Callable, Protocol
from pathlib import Path

from models import Task, TaskStatus, EventSource, EventLog, asdict, ExecutionResult
from storage import TaskStorage, StorageError

logger = logging.getLogger(__name__)


class TaskExecutor(Protocol):
    """任务执行器协议 - 定义如何执行任务"""

    def execute(self, task: Task) -> ExecutionResult:
        """
        执行任务

        Args:
            task: 任务对象

        Returns:
            执行结果
        """
        ...


class QoderWorker:
    """Qoder Worker - 任务执行器"""

    def __init__(
        self,
        tasks_dir: str = "bridge/tasks",
        poll_interval: float = 5.0,
        executor: Optional[TaskExecutor] = None
    ):
        """
        初始化 Worker

        Args:
            tasks_dir: 任务文件目录
            poll_interval: 轮询间隔（秒）
            executor: 任务执行器（不提供则使用默认的模拟执行器）
        """
        self.storage = TaskStorage(tasks_dir)
        self.poll_interval = poll_interval
        self.executor = executor

    def claim_task(self, task: Task) -> bool:
        """
        认领任务（将状态从 queued 改为 claimed）

        Args:
            task: 待认领的任务

        Returns:
            是否认领成功
        """
        if task.status != TaskStatus.QUEUED.value:
            logger.debug(f"任务 {task.task_id} 状态不是 queued，跳过")
            return False

        # 更新状态
        updated = self.storage.update_task_status(
            task.task_id,
            TaskStatus.CLAIMED,
            EventSource.QODER,
            "Qoder 已认领任务"
        )

        if updated:
            # 记录认领时间
            self.storage.update_execution(
                task.task_id,
                claimed_at=datetime.now(timezone.utc).isoformat()
            )
            logger.info(f"已认领任务: {task.task_id}")
            return True

        return False

    def start_execution(self, task: Task) -> bool:
        """
        开始执行任务（将状态从 claimed 改为 running）

        Args:
            task: 任务

        Returns:
            是否成功
        """
        if task.status != TaskStatus.CLAIMED.value:
            return False

        updated = self.storage.update_task_status(
            task.task_id,
            TaskStatus.RUNNING,
            EventSource.QODER,
            "开始执行任务"
        )

        if updated:
            self.storage.update_execution(
                task.task_id,
                started_at=datetime.now(timezone.utc).isoformat()
            )
            logger.info(f"开始执行任务: {task.task_id}")
            return True

        return False

    def update_progress(
        self,
        task_id: str,
        current_step: str,
        changed_files: List[str] = None,
        test_results: List[dict] = None,
        next_action: str = ""
    ) -> None:
        """
        更新执行进度

        Args:
            task_id: 任务ID
            current_step: 当前步骤描述
            changed_files: 已修改的文件列表
            test_results: 测试结果
            next_action: 下一步动作
        """
        update_data = {"current_step": current_step}

        if changed_files is not None:
            # 追加而非覆盖
            task = self.storage.load_task(task_id)
            if task:
                existing = task.execution.changed_files or []
                all_files = list(set(existing + changed_files))
                update_data["changed_files"] = all_files

        if test_results is not None:
            update_data["test_results"] = test_results

        if next_action:
            update_data["next_action"] = next_action

        self.storage.update_execution(task_id, **update_data)

        # 追加事件日志
        self.storage.append_event_log(
            task_id,
            EventSource.QODER,
            "progress_update",
            f"进度更新: {current_step}"
        )

    def complete_success(
        self,
        task_id: str,
        result_summary: str,
        changed_files: List[str] = None,
        test_results: List[dict] = None
    ) -> None:
        """
        标记任务成功完成

        Args:
            task_id: 任务ID
            result_summary: 结果摘要
            changed_files: 修改的文件列表
            test_results: 测试结果
        """
        # 更新执行结果
        update_data = {
            "result_summary": result_summary,
            "finished_at": datetime.now(timezone.utc).isoformat()
        }

        if changed_files:
            update_data["changed_files"] = changed_files
        if test_results:
            update_data["test_results"] = test_results

        self.storage.update_execution(task_id, **update_data)

        # 更新状态
        self.storage.update_task_status(
            task_id,
            TaskStatus.SUCCESS,
            EventSource.QODER,
            f"任务完成: {result_summary}"
        )

        logger.info(f"任务成功完成: {task_id}")

    def complete_failure(
        self,
        task_id: str,
        error_message: str,
        result_summary: str = ""
    ) -> None:
        """
        标记任务执行失败

        Args:
            task_id: 任务ID
            error_message: 错误信息
            result_summary: 结果摘要
        """
        self.storage.update_execution(
            task_id,
            error_message=error_message,
            result_summary=result_summary or f"执行失败: {error_message}",
            finished_at=datetime.now(timezone.utc).isoformat()
        )

        self.storage.update_task_status(
            task_id,
            TaskStatus.FAILED,
            EventSource.QODER,
            f"任务失败: {error_message}"
        )

        logger.error(f"任务执行失败: {task_id} - {error_message}")

    def execute_single_task(self, task: Task) -> bool:
        """
        执行单个任务

        Args:
            task: 任务对象

        Returns:
            是否成功
        """
        try:
            # 认领任务
            if not self.claim_task(task):
                return False

            # 开始执行
            if not self.start_execution(task):
                return False

            # 执行任务
            if self.executor:
                result = self.executor.execute(task)

                # 根据结果更新状态
                if result.error_message:
                    self.complete_failure(
                        task.task_id,
                        result.error_message,
                        result.result_summary
                    )
                else:
                    self.complete_success(
                        task.task_id,
                        result.result_summary,
                        result.changed_files,
                        result.test_results
                    )

                # 更新最终执行信息
                self.storage.update_execution(
                    task.task_id,
                    current_step="执行完成",
                    next_action=""
                )

            else:
                logger.warning(f"任务 {task.task_id} 没有配置执行器")
                self.complete_failure(task.task_id, "没有配置执行器")

            return True

        except Exception as e:
            logger.exception(f"执行任务 {task.task_id} 时发生异常")
            self.complete_failure(task.task_id, str(e))
            return False

    def run_once(self) -> int:
        """
        执行一轮：查找并执行所有待处理任务

        Returns:
            处理的的任务数量
        """
        queued_tasks = self.storage.get_queued_tasks()
        processed = 0

        for task in queued_tasks:
            if self.execute_single_task(task):
                processed += 1

        return processed

    def run_loop(self, max_iterations: Optional[int] = None) -> None:
        """
        持续运行 Worker

        Args:
            max_iterations: 最大迭代次数，None 表示永不停止
        """
        iterations = 0

        logger.info(f"Qoder Worker 启动，轮询间隔: {self.poll_interval}s")

        try:
            while max_iterations is None or iterations < max_iterations:
                try:
                    processed = self.run_once()

                    if processed > 0:
                        logger.info(f"本轮处理了 {processed} 个任务")

                except Exception as e:
                    logger.exception(f"轮询时发生异常: {e}")

                iterations += 1
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Worker 被用户中断")

        logger.info(f"Worker 已停止，共运行 {iterations} 轮")


class CallbackExecutor:
    """基于回调函数的任务执行器"""

    def __init__(
        self,
        on_progress: Callable[[Task, str], None] = None,
        on_file_changed: Callable[[Task, str], None] = None,
        on_complete: Callable[[Task], dict] = None
    ):
        """
        初始化回调执行器

        Args:
            on_progress: 进度回调 (task, step) -> None
            on_file_changed: 文件变更回调 (task, filepath) -> None
            on_complete: 完成回调 (task) -> dict (返回执行结果)
        """
        self.on_progress = on_progress
        self.on_file_changed = on_file_changed
        self.on_complete = on_complete

    def execute(self, task: Task) -> ExecutionResult:
        """执行任务"""
        result = ExecutionResult()

        try:
            # 调用完成回调
            if self.on_complete:
                exec_result = self.on_complete(task)

                result.changed_files = exec_result.get("changed_files", [])
                result.test_results = exec_result.get("test_results", [])
                result.result_summary = exec_result.get("result_summary", "")
                result.error_message = exec_result.get("error_message", "")

        except Exception as e:
            result.error_message = str(e)

        return result
