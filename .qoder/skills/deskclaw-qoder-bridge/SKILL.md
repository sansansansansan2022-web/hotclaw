---
name: deskclaw-qoder-bridge
description: DeskClaw 与 Qoder 协作桥接技能。通过 JSON 任务文件实现需求编排与代码执行的协作闭环。适用于远程代码开发、手机端任务下发场景。
---

# DeskClaw-Qoder 协作桥接

## 概述

这是一个"单任务文件桥接"方案，让 DeskClaw 作为远程需求编排助理，Qoder 作为本地代码执行代理，两者通过结构化 JSON 任务文件进行协作。

## 架构

```
用户 (飞书)
    ↓
DeskClaw (需求理解、任务分解)
    ↓ 写入 task_xxx.json
任务文件 (bridge/tasks/)
    ↑ 读取
Qoder Worker (轮询、执行、结果回写)
    ↓
Reporter (监听变化、生成中文汇报)
    ↓
用户 (飞书)
```

## 核心文件

| 文件 | 职责 |
|------|------|
| `scripts/models.py` | 数据模型定义 |
| `scripts/storage.py` | 原子文件存储 |
| `scripts/deskclaw_publisher.py` | DeskClaw 发布端 |
| `scripts/qoder_worker.py` | Qoder 执行端 |
| `scripts/reporter.py` | 汇报生成器 |
| `scripts/cli.py` | 命令行入口 |

## 任务状态机

```
queued → claimed → running → success
                        ↘ failed
queued → cancelled
```

## 字段职责分离

| 角色 | 负责字段 |
|------|----------|
| DeskClaw | title, user_request, decomposition, constraints |
| Qoder | execution, status (执行阶段), changed_files, test_results |
| Reporter | 只读，不修改任务主体 |

## 命令行用法

### 发布任务

```bash
python scripts/cli.py publish "帮我修改 app.py，添加用户登录功能" --project myapp
```

### 启动 Worker

```bash
# 使用模拟执行器
python scripts/cli.py worker --mock

# 使用真实执行器
python scripts/cli.py worker

# 单轮执行
python scripts/cli.py worker --once
```

### 启动 Reporter

```bash
python scripts/cli.py reporter
```

### 同时启动 Worker + Reporter

```bash
python scripts/cli.py start-all
```

### 查看状态

```bash
# 查看所有任务
python scripts/cli.py status

# 查看指定任务
python scripts/cli.py status --task-id abc12345
```

### 取消任务

```bash
python scripts/cli.py cancel abc12345 --reason "需求变更"
```

## Python API 用法

### 发布任务

```python
from deskclaw_publisher import publish_task

task = publish_task(
    user_request="帮我添加用户注册功能",
    project="myapp",
    tasks_dir="bridge/tasks"
)
print(f"任务ID: {task.task_id}")
```

### 启动 Worker

```python
from qoder_worker import QoderWorker
from mock_qoder_executor import MockQoderExecutor

executor = MockQoderExecutor()
worker = QoderWorker(tasks_dir="bridge/tasks", executor=executor)

# 单轮执行
worker.run_once()

# 持续运行
worker.run_loop()
```

### 启动 Reporter

```python
from reporter import create_console_reporter

reporter = create_console_reporter(tasks_dir="bridge/tasks")
reporter.run_loop()
```

## 事件日志

每次状态更新都会追加事件日志：

```json
{
  "ts": "2026-03-26T10:30:00+00:00",
  "by": "qoder",
  "event": "progress_update",
  "message": "进度更新: 正在修改 API 路由"
}
```

## 汇报格式

Reporter 会生成简洁的中文汇报：

```
[10:30:01] [abc12345] 开始执行任务
[10:30:05] [abc12345] 进度更新: 正在修改 API 路由
[10:30:10] [abc12345] 任务完成: 已完成 3 个操作，修改了 2 个文件，测试 2/2 通过
```

## 扩展指南

### 接入真实 Qoder 执行器

创建自定义执行器实现 `TaskExecutor` 协议：

```python
from qoder_worker import TaskExecutor
from models import Task, ExecutionResult

class MyQoderExecutor(TaskExecutor):
    def execute(self, task: Task) -> ExecutionResult:
        # TODO: 接入 Qoder 的真实代码执行能力
        pass
```

### 使用 watchdog 监听文件变化

当前默认使用轮询，如需更高效的监听：

```python
# 安装 watchdog
# pip install watchdog

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TaskFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        # 处理文件变化
        pass

observer = Observer()
observer.schedule(TaskFileHandler(), path="bridge/tasks", recursive=False)
observer.start()
```

## 注意事项

1. **原子写入**: 所有文件写入都使用临时文件 + rename 方式
2. **并发安全**: 使用文件锁保护读写操作
3. **版本控制**: 每次更新递增 version 字段
4. **变更检测**: 通过 version 和 event_logs 长度检测变化
5. **去重汇报**: Reporter 只输出新增事件，避免刷屏

## 相关文档

- 详细使用说明: [README.md](README.md)
- 数据模型参考: [scripts/models.py](scripts/models.py)
