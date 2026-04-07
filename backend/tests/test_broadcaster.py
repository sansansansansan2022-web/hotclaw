"""Tests for SSEBroadcaster safeguards."""

import pytest

from app.orchestrator.broadcaster import SSEBroadcaster


@pytest.mark.asyncio
async def test_broadcaster_history_is_capped():
    broadcaster = SSEBroadcaster()
    task_id = "task-history-cap"

    for i in range(250):
        await broadcaster.broadcast(task_id, "node_start", {"i": i})

    history = broadcaster._history[task_id]
    assert len(history) == 200
    # earliest 50 events should be dropped, first retained event should be i=50
    assert history[0]["data"]["i"] == 50
    assert history[-1]["data"]["i"] == 249
