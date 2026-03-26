# DeskClaw-Qoder 协作桥接

本地文件桥接型技能，用于让 DeskClaw 与 Qoder 协作完成远程代码开发任务。

## 目录结构

```
deskclaw-qoder-bridge/
├── SKILL.md                        # 技能说明
├── README.md                       # 本文档
├── scripts/
│   ├── __init__.py                 # 包初始化
│   ├── models.py                   # 数据模型定义
│   ├── storage.py                  # 文件存储模块
│   ├── deskclaw_publisher.py       # DeskClaw 发布端
│   ├── qoder_worker.py             # Qoder 执行端
│   ├── reporter.py                 # 汇报生成器
│   ├── mock_qoder_executor.py      # 模拟执行器
│   └── cli.py                      # 命令行入口
└── bridge/
    └── tasks/                      # 任务文件目录（自动创建）
```

## 快速开始

### 1. 发布任务

```bash
cd deskclaw-qoder-bridge
python scripts/cli.py publish "帮我修改 app.py，添加用户登录功能" --project myapp
```

输出示例：
```
✅ 任务已发布: abc12345
   标题: 帮我修改 app.py，添加用户登录功能
   状态: queued
   分解步骤: 1 个
```

### 2. 启动 Worker 执行任务

```bash
python scripts/cli.py worker --mock
```

### 3. 启动 Reporter 监听变化

新开一个终端：

```bash
python scripts/cli.py reporter
```

## 完整示例流程

### 场景：用户通过飞书提出开发需求

#### Step 1: DeskClaw 发布任务

```bash
python scripts/cli.py publish "添加用户注册和登录功能，包含手机号验证" --project webapp
```

生成的 `bridge/tasks/task_xxx.json`：

```json
{
  "task_id": "a1b2c3d4",
  "version": 1,
  "created_at": "2026-03-26T10:00:00+00:00",
  "updated_at": "2026-03-26T10:00:00+00:00",
  "source": "deskclaw",
  "project": "webapp",
  "title": "添加用户注册和登录功能，包含手机号验证",
  "user_request": "添加用户注册和登录功能，包含手机号验证",
  "decomposition": ["添加用户注册和登录功能，包含手机号验证"],
  "constraints": {"must_do": [], "must_not": []},
  "status": "queued",
  "executor": "qoder",
  "execution": {
    "claimed_at": null,
    "started_at": null,
    "finished_at": null,
    "current_step": "",
    "changed_files": [],
    "test_results": [],
    "result_summary": "",
    "error_message": "",
    "next_action": ""
  },
  "event_logs": [
    {
      "ts": "2026-03-26T10:00:00+00:00",
      "by": "deskclaw",
      "event": "task_created",
      "message": "任务已创建: 添加用户注册和登录功能，包含手机号验证"
    }
  ],
  "report_state": {
    "last_reported_event_index": 0,
    "last_reported_version": 1
  }
}
```

#### Step 2: Qoder Worker 认领并执行

```bash
python scripts/cli.py worker --mock
```

Worker 会：
1. 发现 `status: queued` 的任务
2. 将状态改为 `claimed`
3. 将状态改为 `running`
4. 执行代码修改
5. 回写结果到文件

#### Step 3: Reporter 汇报给用户

Reporter 终端会显示：

```
[10:00:01] [a1b2c3d4] 发现新任务: 添加用户注册和登录功能，包含手机号验证
[10:00:01] [a1b2c3d4] 需求: 添加用户注册和登录功能，包含手机号验证
[10:00:01] [a1b2c3d4] 计划执行 1 个步骤
---
[10:00:05] [a1b2c3d4] Qoder 已认领任务
[10:00:05] [a1b2c3d4] 开始执行任务
[10:00:06] [a1b2c3d4] 进度更新: 分析任务需求
[10:00:07] [a1b2c3d4] 进度更新: 读取相关代码
[10:00:08] [a1b2c3d4] 进度更新: 制定修改方案
[10:00:09] [a1b2c3d4] 进度更新: 执行代码修改
[10:00:10] [a1b2c3d4] 进度更新: 运行测试验证
[10:00:11] [a1b2c3d4] 任务完成: 已完成 1 个操作，修改了 1 个文件，测试 2/2 通过
```

#### Step 4: 查看最终状态

```bash
python scripts/cli.py status --task-id a1b2c3d4
```

输出：
```
[添加用户注册和登录功能，包含手机号验证] 已完成
当前: 执行完成 | 已修改 1 个文件 | 测试: 2/2 通过
任务ID: a1b2c3d4
标题: 添加用户注册和登录功能，包含手机号验证
状态: success
版本: 8
创建时间: 2026-03-26T10:00:00+00:00
更新时间: 2026-03-26T10:00:11+00:00

修改文件:
  - src/new_module.py

测试结果:
  ✅ test_main
  ✅ test_feature
```

## 命令参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `publish` | 发布新任务 | `publish "需求描述" --project myapp` |
| `worker` | 启动 Worker | `worker --mock --interval 5` |
| `reporter` | 启动 Reporter | `reporter --interval 2` |
| `start-all` | 同时启动两者 | `start-all` |
| `status` | 查看状态 | `status` 或 `status -i task_id` |
| `list` | 列出任务 | `list --status queued` |
| `cancel` | 取消任务 | `cancel task_id --reason "原因"` |
| `clean` | 清理已完成任务 | `clean` |

## Python API

### 发布任务

```python
from deskclaw_publisher import DeskClawPublisher

publisher = DeskClawPublisher("bridge/tasks")
task = publisher.create_task(
    user_request="修改用户模块",
    project="myapp",
    title="用户模块修改"
)
```

### 自定义执行器

```python
from qoder_worker import QoderWorker, TaskExecutor
from models import Task, ExecutionResult

class MyExecutor(TaskExecutor):
    def execute(self, task: Task) -> ExecutionResult:
        result = ExecutionResult()
        # 实现你的执行逻辑
        result.result_summary = "执行完成"
        return result

worker = QoderWorker("bridge/tasks", executor=MyExecutor())
worker.run_loop()
```

### 自定义 Reporter

```python
from reporter import TaskReporter

def on_report(task_id, message):
    # 发送到飞书
    print(f"[{task_id}] {message}")

reporter = TaskReporter("bridge/tasks", on_report=on_report)
reporter.run_loop()
```

## 数据模型

### TaskStatus 状态枚举

```python
from models import TaskStatus

TaskStatus.QUEUED     # 待执行
TaskStatus.CLAIMED    # 已认领
TaskStatus.RUNNING    # 执行中
TaskStatus.SUCCESS    # 执行成功
TaskStatus.FAILED     # 执行失败
TaskStatus.CANCELLED  # 已取消
```

### EventSource 事件来源

```python
from models import EventSource

EventSource.DESKCLAW  # DeskClaw 创建
EventSource.QODER     # Qoder 执行
EventSource.REPORTER  # Reporter 汇报
```

## 故障排查

### 文件锁冲突

如果遇到 `PermissionError`，确保没有其他进程正在写入同一任务文件。

### 任务卡在 claimed 状态

检查 Worker 是否正在运行，或手动重置状态：

```python
from storage import TaskStorage
from models import TaskStatus, EventSource

storage = TaskStorage("bridge/tasks")
storage.update_task_status("task_id", TaskStatus.QUEUED, EventSource.DESKCLAW, "手动重置")
```

### Reporter 不输出

检查任务文件是否存在，以及 Reporter 的任务目录是否正确。

## 依赖

- Python 3.11+
- 标准库: `json`, `pathlib`, `fcntl`, `tempfile`, `logging`
- 可选: `watchdog`（如需更高效的文件监听）

## License

MIT
