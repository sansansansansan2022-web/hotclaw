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


class TaskArtifactResponse(BaseModel):
    artifact_key: str
    stage: str
    title: str
    status: str
    display_payload: dict | None = None
    raw_output: dict | None = None
    source_node_ids: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class TaskArtifactListResponse(BaseModel):
    task_id: str
    account_id: str | None = None
    status: str
    artifacts: list[TaskArtifactResponse] = Field(default_factory=list)


class TaskEffectiveInputResponse(BaseModel):
    task_id: str
    account_id: str | None = None
    workflow_id: str
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    positioning: str | None = None
    ops_context: dict | None = None
    explicit_input: dict = Field(default_factory=dict)
    selection_session_id: str | None = None
    selected_recommendations: list = Field(default_factory=list)
    selected_reference_sources: list = Field(default_factory=list)
    compose_preview: dict | None = None
    query_plan: dict | None = None
    reference_digest: dict | None = None
    outline_seed: dict | None = None
    creation_note: str | None = None
    external_evidence: dict | None = None
    input_data: dict = Field(default_factory=dict)


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
    account_id: str | None = None
    account_name: str | None = None
    status: str
    input_data: dict | None = None
    workflow_id: str
    result_data: dict | None = None
    ops_context: dict | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    elapsed_seconds: float | None = None
    total_tokens: int | None = None
    error_message: str | None = None


class TaskSummary(BaseModel):
    task_id: str
    account_id: str | None = None
    account_name: str | None = None
    positioning_summary: str
    status: str
    created_at: datetime
    elapsed_seconds: float | None = None
    error_message: str | None = None
    audit_result: dict | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskSummary]
    pagination: dict
