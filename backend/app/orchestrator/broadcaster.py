"""
SSE Broadcaster: manages server-sent event streams for task status updates.

【SSE 广播器】
管理所有任务的 SSE 事件流，核心功能：
1. 维护 task_id → [订阅者队列] 的映射
2. 事件历史缓冲（新订阅者自动重放）
3. 任务结束时安全关闭所有订阅

设计模式：发布-订阅（Observer Pattern）
- 编排器调用 broadcast() 发布事件
- SSE 路由调用 subscribe() 订阅事件
- asyncio.Queue 作为事件传递的通道

面试点：
- asyncio.Queue 异步队列
- SSE 协议格式（event: / data:）
- 历史缓冲解决 SSE 竞态问题
- call_later 延迟清理防止内存泄漏
"""

import asyncio
import json
from typing import Any
from app.core.logger import get_logger

logger = get_logger(__name__)


class SSEBroadcaster:
    """
    Manages SSE event queues per task_id.

    【SSE 广播器核心】
    前端通过 GET /api/v1/tasks/{task_id}/stream 连接 SSE。
    编排器通过 broadcast() 发布 node_start / node_complete 等事件。
    SSE 端点从订阅队列中读取事件，转发给前端。

    【竞态问题解决】
    场景：任务开始执行 → 前端还未建立 SSE 连接 → 事件丢失
    解决：_history 缓冲已发送事件，新订阅者自动重放全部历史

    Attributes:
        _subscribers: task_id → 订阅者队列列表
        _history: task_id → 历史事件列表（deque，固定长度）
        _closed: task_id → 是否已关闭
    """

    def __init__(self) -> None:
        self._max_history_per_task = 200
        # task_id -> 订阅者队列列表（可能有多个浏览器标签页同时订阅）
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        # task_id -> 历史事件（deque，自动淘汰旧事件）
        self._history: dict[str, list[dict[str, Any]]] = {}
        # task_id -> 任务是否已结束（结束时发送哨兵值 None）
        self._closed: dict[str, bool] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """
        Create a new subscriber queue for a task, replaying past events.

        【订阅方法】SSE 路由调用此方法创建订阅

        流程：
        1. 创建新的 asyncio.Queue 作为事件通道
        2. 将历史事件全部放入队列（重放）
        3. 如果任务已结束，立即放入哨兵值 None（让 SSE 立即关闭）
        4. 否则加入订阅者列表

        Returns:
            asyncio.Queue 事件队列，调用者从队列中读取事件

        【并发安全】此方法同步执行，不需要锁
        因为 Python asyncio 的 Queue 操作在单线程事件循环中是原子的
        """
        queue: asyncio.Queue = asyncio.Queue()

        # 重放历史事件（解决竞态问题）
        for msg in self._history.get(task_id, []):
            queue.put_nowait(msg)  # 同步放入，不阻塞

        # 如果任务已结束，立即发送哨兵值
        if self._closed.get(task_id):
            queue.put_nowait(None)
        else:
            # 追加到订阅者列表
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(queue)

        logger.info("sse_subscribe", task_id=task_id,
                     replayed=len(self._history.get(task_id, [])))
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        """
        Remove a subscriber queue.

        【取消订阅】SSE 连接关闭时调用
        从订阅者列表中移除队列，如果列表为空则删除 task_id 条目
        """
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                # 队列不在列表中（可能已被移除）
                pass
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def broadcast(self, task_id: str, event: str, data: dict[str, Any]) -> None:
        """
        Push an SSE event to all subscribers of a task.

        【广播方法】编排器在每个节点开始/完成/错误时调用

        流程：
        1. 构造消息 payload
        2. 存入 _history（供后续订阅者重放）
        3. 推送给所有当前在线订阅者

        Args:
            task_id: 任务 ID
            event: 事件类型（"node_start" / "node_complete" / "node_error" / "task_complete"）
            data: 事件数据字典
        """
        message = {"event": event, "data": data}

        # 存入历史（限制每个任务的最大缓存，避免长任务内存增长）
        if task_id not in self._history:
            self._history[task_id] = []
        history = self._history[task_id]
        history.append(message)
        if len(history) > self._max_history_per_task:
            # 移除最早的事件，保持固定上限
            del history[0]

        # 推送给所有在线订阅者
        subscribers = self._subscribers.get(task_id, [])
        for queue in subscribers:
            # await queue.put(): 异步放入，如果队列满则等待
            await queue.put(message)

        logger.info("sse_broadcast", task_id=task_id, sse_event=event,
                     subscriber_count=len(subscribers))

    async def close_task(self, task_id: str) -> None:
        """
        Signal end-of-stream to all subscribers and mark task closed.

        【关闭任务流】
        编排器在任务完成后调用，通知所有订阅者流已结束。

        流程：
        1. 标记任务为已关闭
        2. 向所有订阅者发送哨兵值 None（告诉 SSE 路由可以关闭连接）
        3. 删除订阅者列表
        4. 60 秒后清理历史数据（防止内存泄漏）
        """
        self._closed[task_id] = True
        subscribers = self._subscribers.get(task_id, [])

        # 向每个订阅者发送哨兵值
        for queue in subscribers:
            await queue.put(None)

        # 删除订阅者列表
        if task_id in self._subscribers:
            del self._subscribers[task_id]

        # 【关键】60 秒后清理历史
        # 使用 call_later 在事件循环中调度延迟任务
        # 这样即使没有活跃的事件循环也不会报错
        try:
            loop = asyncio.get_running_loop()
            loop.call_later(60, self._cleanup_history, task_id)
        except RuntimeError:
            # 如果没有运行中的事件循环（极少见），跳过清理调度
            pass

    def _cleanup_history(self, task_id: str) -> None:
        """
        Remove buffered history after a grace period.

        【历史清理】60 秒后调用，释放内存
        为什么延迟清理？因为可能有延迟连接的订阅者需要重放历史
        """
        self._history.pop(task_id, None)
        self._closed.pop(task_id, None)

    @staticmethod
    def format_sse(event: str, data: dict) -> str:
        """
        Format an SSE message string.

        【SSE 格式】
        SSE 协议规定每条消息格式为：
            event: <事件类型>
            data: <JSON 数据>
            <空行>

        注意：
        - event: 和 data: 必须各占一行
        - 末尾必须有双换行符（\n\n）表示消息结束
        - JSON 数据中的中文需要 ensure_ascii=False

        SSE 事件类型：
        - node_start: 节点开始执行
        - node_complete: 节点执行完成
        - node_error: 节点执行失败
        - task_complete: 任务全部完成
        - task_error: 任务执行异常
        """
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# 【单例模式】全局广播器实例
# 整个应用共享同一个广播器
broadcaster = SSEBroadcaster()
