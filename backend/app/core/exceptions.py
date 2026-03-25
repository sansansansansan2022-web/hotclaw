"""Unified exception hierarchy for HotClaw."""


class HotClawError(Exception):
    """Base exception for all HotClaw errors."""

    def __init__(self, code: int, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


# --- User input errors (1xxx) ---


class ValidationError(HotClawError):
    """Request parameter validation failed."""

    def __init__(self, message: str = "validation error", details: dict | None = None):
        super().__init__(code=1001, message=message, details=details)


class TaskNotFoundError(HotClawError):
    """Task does not exist."""

    def __init__(self, task_id: str):
        super().__init__(code=1002, message=f"task not found: {task_id}")


class AgentNotFoundError(HotClawError):
    """Agent does not exist."""

    def __init__(self, agent_id: str):
        super().__init__(code=1003, message=f"agent not found: {agent_id}")


class SkillNotFoundError(HotClawError):
    """Skill does not exist."""

    def __init__(self, skill_id: str):
        super().__init__(code=1004, message=f"skill not found: {skill_id}")


# --- Conflict errors (2xxx) ---


class TaskAlreadyRunningError(HotClawError):
    """Task is already running."""

    def __init__(self, task_id: str):
        super().__init__(code=2001, message=f"task already running: {task_id}")


class WorkflowNotFoundError(HotClawError):
    """Workflow definition does not exist."""

    def __init__(self, workflow_id: str):
        super().__init__(code=2002, message=f"workflow not found: {workflow_id}")


# --- External / execution errors (3xxx) ---


class LLMCallError(HotClawError):
    """LLM API call failed."""

    def __init__(self, message: str = "LLM call failed", details: dict | None = None):
        super().__init__(code=3001, message=message, details=details)


class ExternalAPIError(HotClawError):
    """External API call failed."""

    def __init__(self, message: str = "external API call failed", details: dict | None = None):
        super().__init__(code=3002, message=message, details=details)


class AgentTimeoutError(HotClawError):
    """Agent execution timed out."""

    def __init__(self, agent_id: str):
        super().__init__(code=3003, message=f"agent execution timed out: {agent_id}")


class AgentExecutionError(HotClawError):
    """Agent execution failed."""

    def __init__(self, agent_id: str, message: str, details: dict | None = None):
        super().__init__(code=3004, message=f"agent {agent_id} failed: {message}", details=details)


class SkillExecutionError(HotClawError):
    """Skill execution failed."""

    def __init__(self, skill_id: str, message: str, details: dict | None = None):
        super().__init__(code=3005, message=f"skill {skill_id} failed: {message}", details=details)


# --- Config errors (4xxx) ---


class ConfigError(HotClawError):
    """Configuration validation failed."""

    def __init__(self, message: str = "config error", details: dict | None = None):
        super().__init__(code=4001, message=message, details=details)


class ManifestError(HotClawError):
    """Manifest file format error."""

    def __init__(self, message: str = "manifest error", details: dict | None = None):
        super().__init__(code=4002, message=message, details=details)


# --- System errors (5xxx) ---


class InternalError(HotClawError):
    """Internal server error."""

    def __init__(self, message: str = "internal server error", details: dict | None = None):
        super().__init__(code=5000, message=message, details=details)
