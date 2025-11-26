"""Pydantic models for GitHub webhook events and telemetry data."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """Status of a workflow run."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    REQUESTED = "requested"


class WorkflowConclusion(str, Enum):
    """Conclusion of a workflow run."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    NEUTRAL = "neutral"
    STALE = "stale"


class Repository(BaseModel):
    """GitHub repository information."""

    id: int
    name: str
    full_name: str
    private: bool = False
    html_url: str = ""


class Sender(BaseModel):
    """GitHub user who triggered the event."""

    id: int
    login: str
    type: str = "User"


class WorkflowRun(BaseModel):
    """GitHub workflow run information."""

    id: int
    name: str
    workflow_id: int
    head_branch: str = ""
    head_sha: str = ""
    status: str
    conclusion: str | None = None
    run_number: int
    run_attempt: int = 1
    event: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    run_started_at: datetime | None = None
    html_url: str = ""


class Step(BaseModel):
    """GitHub workflow step information."""

    name: str
    status: str
    conclusion: str | None = None
    number: int
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowJob(BaseModel):
    """GitHub workflow job information."""

    id: int
    name: str
    run_id: int
    workflow_name: str = ""
    status: str
    conclusion: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    html_url: str = ""
    runner_name: str | None = None
    runner_group_name: str | None = None
    labels: list[str] = Field(default_factory=list)
    steps: list[Step] = Field(
        default_factory=list,
        description="List of job steps with their execution status and timing",
    )


class WorkflowRunEvent(BaseModel):
    """GitHub workflow_run webhook event payload."""

    action: str
    workflow_run: WorkflowRun
    repository: Repository
    sender: Sender


class WorkflowJobEvent(BaseModel):
    """GitHub workflow_job webhook event payload."""

    action: str
    workflow_job: WorkflowJob
    repository: Repository
    sender: Sender


class QueueMessage(BaseModel):
    """Message structure for the Azure Storage Queue."""

    event_type: str
    delivery_id: str
    received_at: datetime
    payload: dict[str, Any]


class WorkflowMetrics(BaseModel):
    """Enriched workflow metrics for telemetry."""

    # Identifiers
    workflow_run_id: int
    workflow_id: int
    workflow_name: str
    run_number: int
    run_attempt: int

    # Repository info
    repository_id: int
    repository_name: str
    repository_full_name: str

    # Timing
    status: str
    conclusion: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    queue_duration_seconds: float | None = None

    # Context
    event_trigger: str = ""
    head_branch: str = ""
    head_sha: str = ""
    triggered_by: str = ""

    # Metadata
    event_type: str
    action: str
    processed_at: datetime


class JobMetrics(BaseModel):
    """Enriched job metrics for telemetry."""

    # Identifiers
    job_id: int
    job_name: str
    workflow_run_id: int
    workflow_name: str

    # Repository info
    repository_id: int
    repository_name: str
    repository_full_name: str

    # Timing
    status: str
    conclusion: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    queue_duration_seconds: float | None = None

    # Runner info
    runner_name: str | None = None
    runner_group_name: str | None = None
    labels: list[str] = Field(default_factory=list)

    # Metadata
    event_type: str
    action: str
    processed_at: datetime

    # Steps
    steps: list[Step] = Field(default_factory=list)
