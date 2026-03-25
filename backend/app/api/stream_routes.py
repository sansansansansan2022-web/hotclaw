"""SSE stream route for real-time task status updates."""

import asyncio
import json
from fastapi import APIRouter
from starlette.requests import Request
from sse_starlette.sse import EventSourceResponse

from app.orchestrator.broadcaster import broadcaster

router = APIRouter(prefix="/api/v1/tasks", tags=["stream"])


@router.get("/{task_id}/stream")
async def task_event_stream(task_id: str, request: Request) -> EventSourceResponse:
    """SSE endpoint for real-time task execution events."""

    async def event_generator():
        queue = broadcaster.subscribe(task_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield {"comment": "keepalive"}
                    continue

                if message is None:
                    # End-of-stream sentinel
                    break

                yield {
                    "event": message["event"],
                    "data": json.dumps(message["data"], ensure_ascii=False, default=str),
                }
        finally:
            broadcaster.unsubscribe(task_id, queue)

    return EventSourceResponse(event_generator())
