"""SSE Broadcaster: manages server-sent event streams for task status updates."""

import asyncio
import json
from typing import Any
from app.core.logger import get_logger

logger = get_logger(__name__)


class SSEBroadcaster:
    """Manages SSE event queues per task_id.

    Frontend connects via GET /api/v1/tasks/{task_id}/stream.
    The orchestrator pushes events here; SSE endpoint reads from the queue.

    Includes event buffering so late-joining subscribers receive
    all past events (solves the race condition where the task starts
    executing before the frontend SSE connection is established).
    """

    def __init__(self) -> None:
        # task_id -> list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        # task_id -> list of past events (for replay)
        self._history: dict[str, list[dict[str, Any]]] = {}
        # task_id -> whether task stream is closed
        self._closed: dict[str, bool] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """Create a new subscriber queue for a task, replaying past events."""
        queue: asyncio.Queue = asyncio.Queue()
        # Replay buffered history
        for msg in self._history.get(task_id, []):
            queue.put_nowait(msg)
        # If task already closed, send sentinel immediately
        if self._closed.get(task_id):
            queue.put_nowait(None)
        else:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(queue)
        logger.info("sse_subscribe", task_id=task_id,
                     replayed=len(self._history.get(task_id, [])))
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        if task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def broadcast(self, task_id: str, event: str, data: dict[str, Any]) -> None:
        """Push an SSE event to all subscribers of a task."""
        message = {"event": event, "data": data}
        # Buffer for late-joining subscribers
        if task_id not in self._history:
            self._history[task_id] = []
        self._history[task_id].append(message)
        # Push to live subscribers
        subscribers = self._subscribers.get(task_id, [])
        for queue in subscribers:
            await queue.put(message)
        logger.info("sse_broadcast", task_id=task_id, sse_event=event, subscriber_count=len(subscribers))

    async def close_task(self, task_id: str) -> None:
        """Signal end-of-stream to all subscribers and mark task closed."""
        self._closed[task_id] = True
        subscribers = self._subscribers.get(task_id, [])
        for queue in subscribers:
            await queue.put(None)  # Sentinel to signal stream end
        if task_id in self._subscribers:
            del self._subscribers[task_id]
        # Schedule history cleanup after 60s to avoid memory leak
        asyncio.get_event_loop().call_later(60, self._cleanup_history, task_id)

    def _cleanup_history(self, task_id: str) -> None:
        """Remove buffered history after a grace period."""
        self._history.pop(task_id, None)
        self._closed.pop(task_id, None)

    @staticmethod
    def format_sse(event: str, data: dict) -> str:
        """Format an SSE message string."""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# Singleton instance
broadcaster = SSEBroadcaster()
