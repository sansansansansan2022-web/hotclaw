"""Base class for all agents.

Per NOTICE.md section 6:
- Agent is a workflow node role responsible for a single business task
- Has clear input/output
- Returns structured JSON
- Can call Skills
- Should not have multiple responsibilities
"""

from abc import ABC, abstractmethod
from typing import Any
from app.core.logger import get_logger

logger = get_logger(__name__)


class AgentResult:
    """Standardized agent result per NOTICE.md section 8.2."""

    def __init__(
        self,
        status: str,
        agent_name: str,
        data: dict | None = None,
        error: dict | None = None,
        trace_id: str = "",
    ):
        self.status = status
        self.agent_name = agent_name
        self.data = data
        self.error = error
        self.trace_id = trace_id

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "agent_name": self.agent_name,
            "data": self.data,
            "error": self.error,
            "trace_id": self.trace_id,
        }

    @property
    def is_success(self) -> bool:
        return self.status == "success"


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    agent_id: str = ""
    name: str = ""
    description: str = ""
    default_system_prompt: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def get_system_prompt(self, context: dict) -> str:
        """Get the effective system prompt from context, falling back to default."""
        return context.get("system_prompt") or self.default_system_prompt

    @abstractmethod
    async def execute(self, input_data: dict, context: dict) -> AgentResult:
        """Execute the agent's task.

        Args:
            input_data: Structured input data for this agent.
            context: Workspace context (read-only reference to previous agent outputs).

        Returns:
            AgentResult with structured output.
        """
        ...

    async def fallback(self, error: Exception, input_data: dict) -> AgentResult | None:
        """Fallback strategy when execution fails. Override to provide degradation.

        Returns None by default (no fallback).
        """
        return None

    def _success(self, data: dict, trace_id: str = "") -> AgentResult:
        return AgentResult(
            status="success",
            agent_name=self.agent_id,
            data=data,
            trace_id=trace_id,
        )

    def _failure(self, code: str, message: str, trace_id: str = "") -> AgentResult:
        return AgentResult(
            status="failed",
            agent_name=self.agent_id,
            error={"code": code, "message": message},
            trace_id=trace_id,
        )
