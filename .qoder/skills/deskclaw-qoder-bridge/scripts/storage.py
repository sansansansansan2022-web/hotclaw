# -*- coding: utf-8 -*-
"""
文件存储模块
负责任务的原子读写、版本控制、并发安全
"""

import json
import os
import shutil
import tempfile
import logging
import sys

# 跨平台文件锁支持
if sys.platform == 'win32':
    import msvcrt
    _LOCK_TYPE = 'windows'
else:
    import fcntl
    _LOCK_TYPE = 'unix'

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from contextlib import contextmanager

from models import Task, TaskStatus, EventLog, EventSource, asdict

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """存储相关错误"""
    pass


class TaskStorage:
    """任务文件存储器"""

    def __init__(self, tasks_dir: str = "bridge/tasks"):
        """
        初始化存储器

        Args:
            tasks_dir: 任务文件存储目录
        """
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def _get_task_path(self, task_id: str) -> Path:
        """获取任务文件路径"""
        return self.tasks_dir / f"task_{task_id}.json"

    @contextmanager
    def _file_lock(self, filepath: Path, mode: str = "r"):
        """
        文件锁上下文管理器
        跨平台支持：Unix 使用 flock，Windows 使用简化实现
        """
        # Windows 简化实现（依赖操作系统本身的文件保护）
        if _LOCK_TYPE == 'windows':
            yield
            return

        # Unix: 使用 flock
        lock_path = Path(str(filepath) + ".lock")

        with open(lock_path, 'w') as lock_file:
            try:
                fcntl.flock(lock_file.fileno(),
                           fcntl.LOCK_EX if mode == 'w' else fcntl.LOCK_SH)
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _atomic_write(self, filepath: Path, data: dict) -> None:
        """
        原子写入：先写临时文件，再 rename
        确保写入不会损坏原文件
        """
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(
            dir=filepath.parent,
            prefix='.tmp_',
            suffix='.json'
        )

        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 原子替换
            shutil.move(temp_path, filepath)
            logger.debug(f"原子写入成功: {filepath}")

        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise StorageError(f"原子写入失败: {e}") from e

    def save_task(self, task: Task) -> None:
        """
        保存任务到文件（原子写入）

        Args:
            task: 任务对象

        Raises:
            StorageError: 保存失败时
        """
        task_path = self._get_task_path(task.task_id)

        # 更新版本和时间戳
        task.version += 1
        task.updated_at = datetime.now(timezone.utc).isoformat()

        with self._file_lock(task_path, mode='w'):
            try:
                data = task.to_dict()
                self._atomic_write(task_path, data)
                logger.info(f"任务已保存: {task.task_id}")
            except Exception as e:
                raise StorageError(f"保存任务失败 {task.task_id}: {e}") from e

    def load_task(self, task_id: str) -> Optional[Task]:
        """
        加载任务文件

        Args:
            task_id: 任务ID

        Returns:
            Task 对象，文件不存在返回 None

        Raises:
            StorageError: 文件损坏或解析失败
        """
        task_path = self._get_task_path(task_id)

        if not task_path.exists():
            return None

        with self._file_lock(task_path, mode='r'):
            try:
                with open(task_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return Task.from_dict(data)
            except json.JSONDecodeError as e:
                raise StorageError(f"任务文件 JSON 解析失败 {task_id}: {e}")
            except Exception as e:
                raise StorageError(f"加载任务失败 {task_id}: {e}")

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务文件

        Args:
            task_id: 任务ID

        Returns:
            是否成功删除
        """
        task_path = self._get_task_path(task_id)

        if not task_path.exists():
            return False

        with self._file_lock(task_path, mode='w'):
            try:
                os.unlink(task_path)
                logger.info(f"任务已删除: {task_id}")
                return True
            except Exception as e:
                logger.error(f"删除任务失败 {task_id}: {e}")
                return False

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """
        列出所有任务

        Args:
            status: 可选，按状态过滤

        Returns:
            任务列表
        """
        tasks = []

        for task_file in self.tasks_dir.glob("task_*.json"):
            try:
                with open(task_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                task = Task.from_dict(data)

                if status is None or task.status == status.value:
                    tasks.append(task)

            except Exception as e:
                logger.warning(f"跳过损坏的任务文件 {task_file}: {e}")
                continue

        # 按更新时间倒序
        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        return tasks

    def get_queued_tasks(self) -> List[Task]:
        """获取所有待执行的任务"""
        return self.list_tasks(status=TaskStatus.QUEUED)

    def update_task_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        source: EventSource,
        message: str = ""
    ) -> Optional[Task]:
        """
        更新任务状态（带锁保护）

        Args:
            task_id: 任务ID
            new_status: 新状态
            source: 事件来源
            message: 事件消息

        Returns:
            更新后的任务，失败返回 None
        """
        task = self.load_task(task_id)
        if task is None:
            logger.error(f"任务不存在: {task_id}")
            return None

        if not task.can_transition_to(new_status):
            logger.error(
                f"状态流转非法: {task.task_id} "
                f"{task.status} -> {new_status.value}"
            )
            return None

        task.transition_to(new_status, source, message)
        self.save_task(task)

        return task

    def append_event_log(
        self,
        task_id: str,
        source: EventSource,
        event: str,
        message: str
    ) -> Optional[Task]:
        """
        追加事件日志

        Args:
            task_id: 任务ID
            source: 事件来源
            event: 事件类型
            message: 事件消息

        Returns:
            更新后的任务
        """
        task = self.load_task(task_id)
        if task is None:
            return None

        event_log = EventLog.create(source, event, message)
        task.event_logs.append(asdict(event_log))
        self.save_task(task)

        return task

    def update_execution(
        self,
        task_id: str,
        **kwargs
    ) -> Optional[Task]:
        """
        更新执行信息（只更新 execution 字段）

        Args:
            task_id: 任务ID
            **kwargs: execution 字段的键值对

        Returns:
            更新后的任务
        """
        task = self.load_task(task_id)
        if task is None:
            return None

        for key, value in kwargs.items():
            if hasattr(task.execution, key):
                setattr(task.execution, key, value)

        self.save_task(task)
        return task

    def get_task_file_mtime(self, task_id: str) -> Optional[float]:
        """获取任务文件的修改时间"""
        task_path = self._get_task_path(task_id)
        if task_path.exists():
            return task_path.stat().st_mtime
        return None

    def watch_tasks(self, callback, interval: float = 1.0, timeout: Optional[float] = None):
        """
        轮询监听任务目录变化

        Args:
            callback: 文件变化时的回调函数 (task_id, mtime) -> None
            interval: 轮询间隔（秒）
            timeout: 超时时间（秒），None 表示永不超时
        """
        import time

        last_mtimes = {}
        start_time = time.time()

        # 初始化：记录当前所有文件的 mtime
        for task_file in self.tasks_dir.glob("task_*.json"):
            task_id = task_file.stem.replace("task_", "")
            last_mtimes[task_id] = task_file.stat().st_mtime

        while True:
            if timeout and (time.time() - start_time) > timeout:
                break

            changed = []

            for task_file in self.tasks_dir.glob("task_*.json"):
                task_id = task_file.stem.replace("task_", "")
                current_mtime = task_file.stat().st_mtime

                if task_id not in last_mtimes:
                    # 新文件
                    changed.append((task_id, current_mtime))
                    last_mtimes[task_id] = current_mtime
                elif current_mtime > last_mtimes[task_id]:
                    # 文件已修改
                    changed.append((task_id, current_mtime))
                    last_mtimes[task_id] = current_mtime

            # 检查已删除的文件
            for task_id in list(last_mtimes.keys()):
                if not (self.tasks_dir / f"task_{task_id}.json").exists():
                    last_mtimes.pop(task_id)

            # 触发回调
            for task_id, mtime in changed:
                try:
                    callback(task_id, mtime)
                except Exception as e:
                    logger.error(f"回调处理失败 {task_id}: {e}")

            time.sleep(interval)
