# -*- coding: utf-8 -*-
"""
Reporter 模块
持续监听任务文件变化，生成简洁的中文汇报
只汇报新增内容，避免重复刷屏
"""

import logging
import time
from datetime import datetime
from typing import Optional, List, Callable, Dict
from pathlib import Path

from models import Task, TaskStatus, EventSource, ReportState, generate_progress_report
from storage import TaskStorage

logger = logging.getLogger(__name__)


class TaskReporter:
    """任务汇报器 - 检测变更并生成汇报"""

    def __init__(
        self,
        tasks_dir: str = "bridge/tasks",
        poll_interval: float = 2.0,
        on_report: Callable[[str, str], None] = None  # (task_id, report) -> None
    ):
        """
        初始化汇报器

        Args:
            tasks_dir: 任务文件目录
            poll_interval: 轮询间隔（秒）
            on_report: 汇报回调函数
        """
        self.storage = TaskStorage(tasks_dir)
        self.poll_interval = poll_interval
        self.on_report = on_report

        # 缓存已汇报的状态 {task_id: last_event_index}
        self._reported_states: Dict[str, ReportState] = {}

    def _should_report(self, task: Task) -> bool:
        """
        判断是否需要汇报

        Args:
            task: 任务对象

        Returns:
            是否需要汇报
        """
        task_id = task.task_id

        if task_id not in self._reported_states:
            # 首次发现，需要汇报
            self._reported_states[task_id] = ReportState(
                last_reported_event_index=len(task.event_logs) - 1,
                last_reported_version=task.version
            )
            return True

        cached = self._reported_states[task_id]

        # 检查是否有新的事件日志
        new_events = len(task.event_logs) - cached.last_reported_event_index

        # 检查版本是否变化
        version_changed = task.version > cached.last_reported_version

        return new_events > 0 or version_changed

    def _generate_event_report(
        self,
        task: Task,
        from_index: int
    ) -> List[str]:
        """
        从指定索引开始生成事件汇报

        Args:
            task: 任务对象
            from_index: 起始事件索引

        Returns:
            汇报文本列表
        """
        reports = []
        events = task.event_logs[from_index + 1:]  # 从下一个事件开始

        for event in events:
            ts = event.get("ts", "")
            by = event.get("by", "")
            event_type = event.get("event", "")
            message = event.get("message", "")

            # 格式化时间
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except:
                time_str = ts[11:19] if len(ts) > 19 else ts

            # 根据事件类型生成不同风格的汇报
            if event_type == "task_created":
                reports.append(f"[{time_str}] {message}")
            elif event_type.startswith("status_"):
                reports.append(f"[{time_str}] {message}")
            elif event_type == "progress_update":
                reports.append(f"[{time_str}] {message}")
            else:
                reports.append(f"[{time_str}] [{by}] {message}")

        return reports

    def _generate_status_report(self, task: Task) -> Optional[str]:
        """
        生成状态变化汇报

        Args:
            task: 任务对象

        Returns:
            汇报文本
        """
        return generate_progress_report(task)

    def report_task(self, task: Task) -> List[str]:
        """
        汇报单个任务的变化

        Args:
            task: 任务对象

        Returns:
            汇报文本列表
        """
        task_id = task.task_id
        reports = []

        if task_id not in self._reported_states:
            # 首次发现，汇报全部内容
            reports.append(f"发现新任务: {task.title}")

            # 汇报需求概要
            if task.user_request:
                reports.append(f"需求: {task.user_request[:100]}...")

            # 汇报分解步骤
            if task.decomposition:
                reports.append(f"计划执行 {len(task.decomposition)} 个步骤")

            # 更新状态
            self._reported_states[task_id] = ReportState(
                last_reported_event_index=len(task.event_logs) - 1,
                last_reported_version=task.version
            )

            return reports

        cached = self._reported_states[task_id]

        # 生成增量汇报
        new_event_reports = self._generate_event_report(task, cached.last_reported_event_index)
        reports.extend(new_event_reports)

        # 如果版本有变化但没有新事件，汇报状态变化
        if task.version > cached.last_reported_version and not new_event_reports:
            status_report = self._generate_status_report(task)
            if status_report:
                reports.append(status_report)

        # 更新缓存
        self._reported_states[task_id] = ReportState(
            last_reported_event_index=len(task.event_logs) - 1,
            last_reported_version=task.version
        )

        return reports

    def scan_and_report(self) -> int:
        """
        扫描所有任务，汇报有变化的任务

        Returns:
            汇报的任务数量
        """
        tasks = self.storage.list_tasks()
        reported_count = 0

        for task in tasks:
            if self._should_report(task):
                reports = self.report_task(task)

                if reports:
                    for report in reports:
                        self._emit_report(task.task_id, report)
                    reported_count += 1

        return reported_count

    def _emit_report(self, task_id: str, message: str) -> None:
        """
        发送汇报

        Args:
            task_id: 任务ID
            message: 汇报消息
        """
        logger.info(f"[{task_id}] {message}")

        if self.on_report:
            self.on_report(task_id, message)
        else:
            # 默认打印到控制台
            print(f"[{task_id}] {message}")

    def run_loop(self, max_iterations: Optional[int] = None) -> None:
        """
        持续运行汇报器

        Args:
            max_iterations: 最大迭代次数
        """
        iterations = 0

        logger.info(f"Reporter 启动，轮询间隔: {self.poll_interval}s")

        try:
            while max_iterations is None or iterations < max_iterations:
                try:
                    reported = self.scan_and_report()

                    if reported > 0:
                        print(f"--- 本轮汇报了 {reported} 个任务 ---")

                except Exception as e:
                    logger.exception(f"汇报时发生异常: {e}")

                iterations += 1
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Reporter 被用户中断")

        logger.info(f"Reporter 已停止，共运行 {iterations} 轮")

    def run_watch_mode(self) -> None:
        """
        使用 Watch 模式持续监听文件变化
        依赖 storage.py 的 watch_tasks 方法
        """
        logger.info("Reporter 启动（Watch 模式）")

        last_reported = {}  # {task_id: last_known_version}

        def on_file_change(task_id: str, mtime: float):
            """文件变化时的回调"""
            task = self.storage.load_task(task_id)
            if task is None:
                return

            # 检查是否已汇报过
            last_ver = last_reported.get(task_id, 0)

            if task.version > last_ver:
                reports = self.report_task(task)
                for report in reports:
                    self._emit_report(task_id, report)
                last_reported[task_id] = task.version

        try:
            self.storage.watch_tasks(on_file_change, interval=self.poll_interval)
        except KeyboardInterrupt:
            logger.info("Reporter 被用户中断")


def create_console_reporter(tasks_dir: str = "bridge/tasks") -> TaskReporter:
    """
    创建控制台汇报器

    Args:
        tasks_dir: 任务目录

    Returns:
        TaskReporter 实例
    """
    def print_report(task_id: str, message: str):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{task_id}] {message}")

    return TaskReporter(tasks_dir=tasks_dir, on_report=print_report)
