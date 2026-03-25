"""Task-related request and response schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


# --- Request ---


class TaskCreateRequest(BaseModel):
    """Request body for creating a new task."""
    positioning: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="User's account positioning description",
    )
    workflow_id: str = Field(
        default="default_pipeline",
        description="Workflow template ID to use",
    )


# --- Response data ---


class TaskProgressData(BaseModel):
    total_nodes: int
    completed_nodes: int
    current_node_index: int


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    current_node: str | None = None
    progress: TaskProgressData | None = None
    started_at: datetime | None = None
    elapsed_seconds: float | None = None


class NodeRunData(BaseModel):
    node_id: str
    agent_id: str
    name: str
    status: str
    input_data: dict | None = None
    output_data: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    elapsed_seconds: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model_used: str | None = None
    degraded: bool = False
    error_message: str | None = None


class TaskDetailResponse(BaseModel):
    task_id: str
    status: str
    input_data: dict | None = None
    workflow_id: str
    result_data: dict | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    elapsed_seconds: float | None = None
    total_tokens: int | None = None


class TaskSummary(BaseModel):
    task_id: str
    positioning_summary: str
    status: str
    created_at: datetime
    elapsed_seconds: float | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskSummary]
    pagination: dict
