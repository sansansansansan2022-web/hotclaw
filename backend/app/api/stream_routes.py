"""
SSE stream route for real-time task status updates.

【SSE 流式路由】
提供 GET /api/v1/tasks/{task_id}/stream 接口，
让前端 EventSource 实时接收任务状态更新。

SSE vs WebSocket：
- SSE：服务端推送，单向通信，更简单，支持自动重连
- WebSocket：双向通信，更复杂，需要心跳保活
- 本场景只需要服务端推送状态，SSE 更合适

SSE 协议要点：
1. Content-Type: text/event-stream
2. 每条消息格式：event: <类型>\ndata: <JSON>\n\n
3. 必须定期发送 keepalive（防止代理超时断开连接）
4. 客户端通过 EventSource API 接收

面试点：
- StreamingResponse + async generator 实现 SSE
- EventSource API 前端使用
- keepalive 保活机制
- 连接断开时优雅清理订阅
"""

import asyncio
import json
from fastapi import APIRouter
from starlette.requests import Request
from sse_starlette.sse import EventSourceResponse

from app.orchestrator.broadcaster import broadcaster

router = APIRouter(prefix="/api/v1/tasks", tags=["stream"])


@router.get("/{task_id}/stream")
async def task_event_stream(task_id: str, request: Request) -> EventSourceResponse:
    """
    SSE endpoint for real-time task execution events.

    【SSE 流端点】

    前端 EventSource 连接示例：
        const es = new EventSource('/api/v1/tasks/xxx/stream');
        es.addEventListener('node_start', (e) => console.log(JSON.parse(e.data)));
        es.addEventListener('node_complete', (e) => console.log(JSON.parse(e.data)));
        es.addEventListener('task_complete', (e) => { es.close(); });

    Returns:
        EventSourceResponse: SSE 流，Content-Type 为 text/event-stream
    """
    async def event_generator():
        """
        异步生成器，持续产生 SSE 事件。

        【关键】async generator 的执行特点：
        1. 函数体在首次迭代时才开始执行
        2. yield 暂停函数，向客户端发送数据
        3. next() 调用时恢复执行
        4. finally 块在生成器被关闭时执行
        """
        # 1. 订阅任务事件
        queue = broadcaster.subscribe(task_id)
        try:
            while True:
                # 2. 检查客户端是否断开连接
                if await request.is_disconnected():
                    break

                # 3. 等待事件（最多等 30 秒）
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # 4. 超时 → 发送 keepalive 注释
                    # keepalive 防止代理/负载均衡器因连接空闲而断开
                    yield {"comment": "keepalive"}
                    continue

                # 5. 收到哨兵值 None → 任务结束，关闭连接
                if message is None:
                    break

                # 6. 发送事件
                yield {
                    "event": message["event"],
                    "data": json.dumps(message["data"], ensure_ascii=False, default=str),
                }

        finally:
            # 7. 连接断开时取消订阅
            # 防止内存泄漏（orphaned 订阅者）
            broadcaster.unsubscribe(task_id, queue)

    return EventSourceResponse(event_generator())
