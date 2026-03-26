# -*- coding: utf-8 -*-
"""
模拟 Qoder 执行器
用于演示完整的闭环协作流程
"""

import logging
import os
import time
import random
from pathlib import Path
from typing import Optional

from models import Task, TaskStatus, ExecutionResult
from qoder_worker import TaskExecutor

logger = logging.getLogger(__name__)


class MockFileSystem:
    """模拟文件系统"""

    def __init__(self, workspace_dir: str = "mock_workspace"):
        """
        初始化模拟文件系统

        Args:
            workspace_dir: 模拟工作区目录
        """
        self.workspace = Path(workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)

        # 模拟的项目目录
        self.projects = {
            "web_app": self.workspace / "web_app",
            "api_service": self.workspace / "api_service",
            "hotclaw": self.workspace / "hotclaw",
        }

        for project_dir in self.projects.values():
            project_dir.mkdir(parents=True, exist_ok=True)

            # 创建一些初始文件
            (project_dir / "README.md").write_text("# 项目说明\n", encoding="utf-8")
            (project_dir / "src").mkdir(exist_ok=True)
            (project_dir / "tests").mkdir(exist_ok=True)

    def create_file(self, project: str, filepath: str, content: str) -> str:
        """
        创建文件

        Args:
            project: 项目名
            filepath: 相对路径
            content: 文件内容

        Returns:
            完整文件路径
        """
        project_dir = self.projects.get(project, self.workspace)
        full_path = project_dir / filepath

        # 确保目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        full_path.write_text(content, encoding="utf-8")
        logger.debug(f"创建文件: {full_path}")

        return str(full_path.relative_to(self.workspace))

    def modify_file(self, project: str, filepath: str, new_content: str) -> str:
        """
        修改文件

        Args:
            project: 项目名
            filepath: 相对路径
            new_content: 新内容

        Returns:
            完整文件路径
        """
        project_dir = self.projects.get(project, self.workspace)
        full_path = project_dir / filepath

        full_path.write_text(new_content, encoding="utf-8")
        logger.debug(f"修改文件: {full_path}")

        return str(full_path.relative_to(self.workspace))

    def delete_file(self, project: str, filepath: str) -> bool:
        """
        删除文件

        Args:
            project: 项目名
            filepath: 相对路径

        Returns:
            是否成功
        """
        project_dir = self.projects.get(project, self.workspace)
        full_path = project_dir / filepath

        if full_path.exists():
            full_path.unlink()
            logger.debug(f"删除文件: {full_path}")
            return True

        return False


class MockQoderExecutor(TaskExecutor):
    """
    模拟 Qoder 执行器
    根据任务需求模拟执行代码修改
    """

    # 模拟的代码模板
    CODE_TEMPLATES = {
        "python": '''# -*- coding: utf-8 -*-
"""Auto-generated module"""

def main():
    """Main entry point"""
    pass

if __name__ == "__main__":
    main()
''',
        "javascript": '''// Auto-generated module

function main() {
    // TODO: implement
}

module.exports = { main };
''',
        "test": '''# -*- coding: utf-8 -*-
"""Test cases"""

import unittest

class TestCases(unittest.TestCase):
    def test_example(self):
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
''',
        "api": '''# -*- coding: utf-8 -*-
"""API endpoints"""

from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})
''',
    }

    def __init__(
        self,
        workspace_dir: str = "mock_workspace",
        simulate_delay: float = 2.0,
        success_rate: float = 0.9
    ):
        """
        初始化模拟执行器

        Args:
            workspace_dir: 模拟工作区
            simulate_delay: 模拟执行延迟（秒）
            success_rate: 模拟成功率 (0-1)
        """
        self.fs = MockFileSystem(workspace_dir)
        self.simulate_delay = simulate_delay
        self.success_rate = success_rate

    def _analyze_task(self, task: Task) -> dict:
        """
        分析任务，决定如何执行

        Args:
            task: 任务对象

        Returns:
            执行计划
        """
        request = task.user_request.lower()
        plan = {
            "changed_files": [],
            "actions": [],
        }

        # 根据关键词确定操作
        if "添加" in task.user_request or "新增" in task.user_request:
            if "测试" in task.user_request:
                plan["actions"].append(("create", "test"))
                plan["changed_files"].append("tests/test_new_feature.py")
            else:
                plan["actions"].append(("create", "python"))
                plan["changed_files"].append("src/new_module.py")

        if "修改" in task.user_request or "更新" in task.user_request:
            plan["actions"].append(("modify", "readme"))

        if "api" in request or "接口" in task.user_request:
            plan["actions"].append(("create", "api"))
            plan["changed_files"].append("src/api.py")

        if "bug" in request or "修复" in task.user_request:
            plan["actions"].append(("fix", "any"))

        # 如果没有匹配的操作，执行默认操作
        if not plan["actions"]:
            plan["actions"].append(("create", "python"))
            plan["changed_files"].append("src/generated.py")

        return plan

    def _simulate_progress(
        self,
        task: Task,
        progress_callback=None
    ) -> None:
        """
        模拟执行进度

        Args:
            task: 任务对象
            progress_callback: 进度回调 (step) -> None
        """
        steps = [
            "分析任务需求...",
            "读取相关代码...",
            "制定修改方案...",
            "执行代码修改...",
            "运行测试验证...",
            "整理执行结果...",
        ]

        for i, step in enumerate(steps):
            if progress_callback:
                progress_callback(step)
            time.sleep(self.simulate_delay / len(steps))

    def execute(self, task: Task) -> ExecutionResult:
        """
        执行任务

        Args:
            task: 任务对象

        Returns:
            执行结果
        """
        result = ExecutionResult()
        result.started_at = task.execution.started_at

        try:
            # 分析任务
            plan = self._analyze_task(task)
            result.current_step = "分析任务需求"

            # 模拟执行进度
            def progress_callback(step):
                result.current_step = step
                logger.info(f"[{task.task_id}] {step}")

            self._simulate_progress(task, progress_callback)

            # 确定项目
            project = task.project or "hotclaw"

            # 执行计划中的操作
            changed_files = []
            for action, file_type in plan["actions"]:
                if action == "create":
                    template = self.CODE_TEMPLATES.get(
                        file_type,
                        self.CODE_TEMPLATES["python"]
                    )
                    filepath = plan["changed_files"][0] if plan["changed_files"] else "src/generated.py"
                    self.fs.create_file(project, filepath, template)
                    changed_files.append(filepath)

                elif action == "modify":
                    readme_path = "README.md"
                    content = self.fs.create_file(
                        project,
                        readme_path,
                        "# 更新于 " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n\n"
                        + task.user_request
                    )
                    changed_files.append(readme_path)

                elif action == "fix":
                    # 模拟修复
                    changed_files.append("src/bugfix.py")
                    self.fs.create_file(
                        project,
                        "src/bugfix.py",
                        "# Bug fix\n# " + task.user_request
                    )

            result.changed_files = changed_files

            # 模拟测试
            time.sleep(self.simulate_delay / 2)

            # 随机决定测试结果
            if random.random() < self.success_rate:
                result.test_results = [
                    {"name": "test_main", "passed": True, "duration": 0.05},
                    {"name": "test_feature", "passed": True, "duration": 0.03},
                ]
            else:
                result.test_results = [
                    {"name": "test_main", "passed": True, "duration": 0.05},
                    {"name": "test_feature", "passed": False, "duration": 0.03, "error": "AssertionError"},
                ]
                result.error_message = "测试失败: test_feature"

            # 生成结果摘要
            file_count = len(result.changed_files)
            test_passed = sum(1 for r in result.test_results if r.get("passed"))
            test_total = len(result.test_results)

            result.result_summary = (
                f"已完成 {len(plan['actions'])} 个操作，"
                f"修改了 {file_count} 个文件，"
                f"测试 {test_passed}/{test_total} 通过"
            )

            result.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

        except Exception as e:
            result.error_message = f"执行异常: {str(e)}"
            result.result_summary = f"执行失败: {str(e)}"
            logger.exception(f"执行任务 {task.task_id} 时发生异常")

        return result


class RealQoderExecutor(TaskExecutor):
    """
    真实 Qoder 执行器
    用于实际代码修改（需要接入 Qoder 的代码执行能力）
    """

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = workspace_dir

    def execute(self, task: Task) -> ExecutionResult:
        """
        执行真实任务

        Args:
            task: 任务对象

        Returns:
            执行结果
        """
        result = ExecutionResult()

        try:
            # TODO: 接入 Qoder 的真实代码执行能力
            # 这里先实现占位逻辑

            logger.info(f"Real executor: processing task {task.task_id}")
            result.current_step = "准备执行"

            # 模拟执行
            time.sleep(1)

            result.result_summary = f"真实执行: {task.title}"
            result.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

        except Exception as e:
            result.error_message = str(e)
            logger.exception(f"Real executor error: {e}")

        return result
