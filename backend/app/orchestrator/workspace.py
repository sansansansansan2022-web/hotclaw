"""Workspace: isolated context container for a single task execution.

Each task creates one workspace. Agents read from and write to the workspace.
"""

from typing import Any
from app.core.logger import get_logger

logger = get_logger(__name__)


class Workspace:
    """Task-scoped context container for agent data sharing."""

    def __init__(self, task_id: str, input_data: dict) -> None:
        self.task_id = task_id
        self._data: dict[str, Any] = {"input": input_data}

    def get(self, key: str) -> Any:
        """Get a value from the workspace by key."""
        return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the workspace."""
        self._data[key] = value
        logger.info("workspace_set", task_id=self.task_id, key=key)

    def get_input(self) -> dict:
        """Get the original task input."""
        return self._data.get("input", {})

    def snapshot(self) -> dict:
        """Return a snapshot of all workspace data (for persistence)."""
        return dict(self._data)

    def extract_for_agent(self, input_mapping: dict[str, str]) -> dict:
        """Extract agent input from workspace using a flat key mapping.

        input_mapping maps agent_input_field -> workspace_key.
        Example: {"profile": "profile", "hot_topics": "hot_topics"}

        For MVP we use simple top-level key mapping, not JSONPath.
        """
        result: dict[str, Any] = {}
        for field_name, workspace_key in input_mapping.items():
            if workspace_key.startswith("input."):
                # Reference to original input
                inner_key = workspace_key[len("input."):]
                result[field_name] = self._data.get("input", {}).get(inner_key)
            else:
                result[field_name] = self._data.get(workspace_key)
        return result
