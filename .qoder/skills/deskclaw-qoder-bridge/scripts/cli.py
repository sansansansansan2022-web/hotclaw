# -*- coding: utf-8 -*-
"""
命令行入口
提供任务发布、Worker 启动、Reporter 启动、状态查看等功能
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from models import Task, TaskStatus, generate_progress_report
from storage import TaskStorage
from deskclaw_publisher import DeskClawPublisher
from qoder_worker import QoderWorker
from reporter import TaskReporter, create_console_reporter
from mock_qoder_executor import MockQoderExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def setup_args() -> argparse.ArgumentParser:
    """设置命令行参数"""
    parser = argparse.ArgumentParser(
        description="DeskClaw-Qoder 协作桥接工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 发布新任务
  python cli.py publish "帮我修改 app.py，添加用户登录功能"

  # 启动 Worker 执行任务
  python cli.py worker

  # 启动 Reporter 监听变化
  python cli.py reporter

  # 同时启动 Worker 和 Reporter
  python cli.py start-all

  # 查看任务状态
  python cli.py status
  python cli.py status --task-id abc123

  # 取消任务
  python cli.py cancel abc123 --reason "需求变更"

  # 查看帮助
  python cli.py --help
        """
    )

    parser.add_argument(
        "--tasks-dir",
        default="bridge/tasks",
        help="任务文件目录 (默认: bridge/tasks)"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # publish 命令
    pub_parser = subparsers.add_parser("publish", help="发布新任务")
    pub_parser.add_argument("request", help="用户需求描述")
    pub_parser.add_argument("--project", "-p", default="", help="项目名称")
    pub_parser.add_argument("--title", "-t", default="", help="任务标题")

    # worker 命令
    worker_parser = subparsers.add_parser("worker", help="启动 Worker 执行任务")
    worker_parser.add_argument(
        "--mock",
        action="store_true",
        help="使用模拟执行器"
    )
    worker_parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="轮询间隔（秒）(默认: 5.0)"
    )
    worker_parser.add_argument(
        "--once",
        action="store_true",
        help="只执行一轮后退出"
    )

    # reporter 命令
    reporter_parser = subparsers.add_parser("reporter", help="启动 Reporter 监听变化")
    reporter_parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="轮询间隔（秒）(默认: 2.0)"
    )

    # start-all 命令
    start_parser = subparsers.add_parser("start-all", help="同时启动 Worker 和 Reporter")

    # status 命令
    status_parser = subparsers.add_parser("status", help="查看任务状态")
    status_parser.add_argument("--task-id", "-i", help="指定任务ID")

    # cancel 命令
    cancel_parser = subparsers.add_parser("cancel", help="取消任务")
    cancel_parser.add_argument("task_id", help="任务ID")
    cancel_parser.add_argument("--reason", "-r", default="", help="取消原因")

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出所有任务")
    list_parser.add_argument("--status", "-s", help="按状态过滤")

    # clean 命令
    clean_parser = subparsers.add_parser("clean", help="清理已完成的任务")

    return parser


def cmd_publish(args) -> int:
    """发布任务命令"""
    publisher = DeskClawPublisher(args.tasks_dir)

    task = publisher.create_task(
        user_request=args.request,
        project=args.project,
        title=args.title
    )

    print(f"[OK] 任务已发布: {task.task_id}")
    print(f"   标题: {task.title}")
    print(f"   状态: {task.status}")
    print(f"   分解步骤: {len(task.decomposition)} 个")

    return 0


def cmd_worker(args) -> int:
    """启动 Worker 命令"""
    # 创建执行器
    if args.mock:
        executor = MockQoderExecutor()
        print("使用模拟执行器")
    else:
        print("使用真实执行器（需要接入 Qoder）")
        from mock_qoder_executor import RealQoderExecutor
        executor = RealQoderExecutor()

    # 创建 Worker
    worker = QoderWorker(
        tasks_dir=args.tasks_dir,
        poll_interval=args.interval,
        executor=executor
    )

    print(f"Worker 启动，任务目录: {args.tasks_dir}")
    print(f"轮询间隔: {args.interval}s")

    if args.once:
        processed = worker.run_once()
        print(f"本轮处理了 {processed} 个任务")
        return 0

    worker.run_loop()
    return 0


def cmd_reporter(args) -> int:
    """启动 Reporter 命令"""
    reporter = create_console_reporter(args.tasks_dir)
    reporter.poll_interval = args.interval

    print(f"Reporter 启动，任务目录: {args.tasks_dir}")
    print(f"轮询间隔: {args.interval}s")
    print("---")

    reporter.run_loop()
    return 0


def cmd_start_all(args) -> int:
    """同时启动 Worker 和 Reporter"""
    import threading

    # 创建执行器
    executor = MockQoderExecutor()

    # Worker 线程
    worker = QoderWorker(
        tasks_dir=args.tasks_dir,
        poll_interval=5.0,
        executor=executor
    )

    # Reporter
    reporter = create_console_reporter(args.tasks_dir)
    reporter.poll_interval = 2.0

    def run_worker():
        print("[Worker] 启动")
        worker.run_loop()

    def run_reporter():
        print("[Reporter] 启动")
        reporter.run_loop()

    # 启动线程
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    reporter_thread = threading.Thread(target=run_reporter, daemon=True)

    worker_thread.start()
    reporter_thread.start()

    print("Worker 和 Reporter 已启动，按 Ctrl+C 停止")

    try:
        worker_thread.join()
        reporter_thread.join()
    except KeyboardInterrupt:
        print("\n正在停止...")

    return 0


def cmd_status(args) -> int:
    """查看状态命令"""
    storage = TaskStorage(args.tasks_dir)

    if args.task_id:
        # 查看指定任务
        task = storage.load_task(args.task_id)

        if task is None:
            print("[X] 任务不存在: {args.task_id}")
            return 1

        print(generate_progress_report(task))
        print()
        print(f"任务ID: {task.task_id}")
        print(f"标题: {task.title}")
        print(f"状态: {task.status}")
        print(f"版本: {task.version}")
        print(f"创建时间: {task.created_at}")
        print(f"更新时间: {task.updated_at}")
        print()

        if task.decomposition:
            print("分解步骤:")
            for i, step in enumerate(task.decomposition, 1):
                print(f"  {i}. {step}")

        if task.execution.changed_files:
            print()
            print("修改文件:")
            for f in task.execution.changed_files:
                print(f"  - {f}")

        if task.execution.test_results:
            print()
            print("测试结果:")
            for r in task.execution.test_results:
                passed = "PASS" if r.get("passed") else "FAIL"
                print(f"  [{passed}] {r.get('name')}")

    else:
        # 列出所有任务
        tasks = storage.list_tasks()

        if not tasks:
            print("暂无任务")
            return 0

        print(f"共 {len(tasks)} 个任务:\n")

        for task in tasks:
            status_icon = {
                "queued": "[Q]",
                "claimed": "[C]",
                "running": "[R]",
                "success": "[OK]",
                "failed": "[X]",
                "cancelled": "-",
            }.get(task.status, "?")

            print(f"{status_icon} [{task.task_id}] {task.title}")
            print(f"   状态: {task.status} | 版本: {task.version} | 更新: {task.updated_at[:19]}")

    return 0


def cmd_cancel(args) -> int:
    """取消任务命令"""
    publisher = DeskClawPublisher(args.tasks_dir)

    task = publisher.cancel_task(args.task_id, args.reason)

    if task:
        print(f"[OK] 任务已取消: {task.task_id}")
    else:
        print(f"[X] 取消失败，可能任务不存在或状态不允许取消")
        return 1

    return 0


def cmd_list(args) -> int:
    """列出任务命令"""
    storage = TaskStorage(args.tasks_dir)

    status_filter = None
    if args.status:
        try:
            status_filter = TaskStatus(args.status)
        except ValueError:
            print(f"❌ 无效状态: {args.status}")
            print(f"可用状态: {[s.value for s in TaskStatus]}")
            return 1

    tasks = storage.list_tasks(status=status_filter)

    if not tasks:
        print("没有匹配的任务")
        return 0

    print(f"共 {len(tasks)} 个任务:\n")

    for task in tasks:
        print(f"[{task.task_id}] {task.title}")
        print(f"   状态: {task.status} | 项目: {task.project or '-'}")

    return 0


def cmd_clean(args) -> int:
    """清理已完成任务"""
    storage = TaskStorage(args.tasks_dir)

    # 找出已完成的任务
    completed_statuses = [TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.CANCELLED]
    tasks_to_clean = []

    for status in completed_statuses:
        tasks = storage.list_tasks(status=status)
        tasks_to_clean.extend(tasks)

    if not tasks_to_clean:
        print("没有需要清理的任务")
        return 0

    print(f"将清理 {len(tasks_to_clean)} 个已完成任务:")
    for task in tasks_to_clean:
        print(f"  - {task.task_id}: {task.title} ({task.status})")

    confirm = input("\n确认清理? (y/N): ")
    if confirm.lower() != 'y':
        print("已取消")
        return 0

    removed = 0
    for task in tasks_to_clean:
        if storage.delete_task(task.task_id):
            removed += 1

    print(f"已清理 {removed} 个任务")
    return 0


def main() -> int:
    """主函数"""
    parser = setup_args()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # 确保任务目录存在
    Path(args.tasks_dir).mkdir(parents=True, exist_ok=True)

    # 执行命令
    commands = {
        "publish": cmd_publish,
        "worker": cmd_worker,
        "reporter": cmd_reporter,
        "start-all": cmd_start_all,
        "status": cmd_status,
        "cancel": cmd_cancel,
        "list": cmd_list,
        "clean": cmd_clean,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        try:
            return cmd_func(args)
        except KeyboardInterrupt:
            print("\n操作已取消")
            return 130
        except Exception as e:
            logger.exception(f"执行命令时发生错误: {e}")
            return 1
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
