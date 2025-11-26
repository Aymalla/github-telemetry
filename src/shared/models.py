"""Pydantic models for GitHub webhook events and telemetry data."""

import json
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
    runner_name: str | None = None
    runner_group_name: str | None = None
    labels: list[str] = Field(default_factory=list)


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


class MetricValue:
    name: str
    min_value: float | None
    max_value: float | None
    total_value: float
    count: int
    attributes: dict[str, Any] | None
    value: float
    values: list[float]
    timestamp: datetime

    def __init__(self, name: str, value: float, timestamp: datetime, attributes: dict | None):
        self.name = name
        self.timestamp = timestamp
        self.min_value = value
        self.max_value = value
        self.total_value = value
        self.count = 1
        self.attributes = attributes
        self.value = value
        self.values = [value]

    def add_value(self, value: float) -> None:
        if self.min_value is None or value < self.min_value:
            self.min_value = value
        if self.max_value is None or value > self.max_value:
            self.max_value = value
        self.total_value += value
        self.count += 1
        self.values.append(value)

        # use average as the representative value
        self.value = self.total_value / self.count

    def to_json(self, indent: int | None = 4) -> str:
        return json.dumps(self.__dict__, indent=indent)

    def __repr__(self) -> str:
        return f"MetricValue(name={self.name}, min={self.min_value}, max={self.max_value}, total={self.total_value}, count={self.count}, attributes={self.attributes}, values={self.values}, timestamp={self.timestamp})"
