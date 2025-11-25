"""Tests for Pydantic models."""

from datetime import UTC, datetime

from src.shared.models import (
    JobMetrics,
    QueueMessage,
    Step,
    WorkflowJobEvent,
    WorkflowMetrics,
    WorkflowRunEvent,
)


class TestQueueMessage:
    """Tests for QueueMessage model."""

    def test_create_queue_message(self) -> None:
        """Test creating a queue message."""
        message = QueueMessage(
            event_type="workflow_run",
            delivery_id="abc123",
            received_at=datetime.now(UTC),
            payload={"action": "completed"},
        )
        assert message.event_type == "workflow_run"
        assert message.delivery_id == "abc123"
        assert message.payload == {"action": "completed"}

    def test_queue_message_serialization(self) -> None:
        """Test serializing and deserializing a queue message."""
        original = QueueMessage(
            event_type="workflow_job",
            delivery_id="def456",
            received_at=datetime.now(UTC),
            payload={"action": "in_progress"},
        )
        json_str = original.model_dump_json()
        restored = QueueMessage.model_validate_json(json_str)

        assert restored.event_type == original.event_type
        assert restored.delivery_id == original.delivery_id
        assert restored.payload == original.payload


class TestWorkflowRunEvent:
    """Tests for WorkflowRunEvent model."""

    def test_parse_workflow_run_event(self) -> None:
        """Test parsing a workflow_run event payload."""
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": 123456,
                "name": "CI",
                "workflow_id": 789,
                "head_branch": "main",
                "head_sha": "abc123",
                "status": "completed",
                "conclusion": "success",
                "run_number": 42,
                "run_attempt": 1,
                "event": "push",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:10:00Z",
                "run_started_at": "2024-01-01T00:01:00Z",
                "html_url": "https://github.com/owner/repo/actions/runs/123456",
            },
            "repository": {
                "id": 111,
                "name": "repo",
                "full_name": "owner/repo",
                "private": False,
                "html_url": "https://github.com/owner/repo",
            },
            "sender": {
                "id": 1,
                "login": "user",
                "type": "User",
            },
        }

        event = WorkflowRunEvent.model_validate(payload)
        assert event.action == "completed"
        assert event.workflow_run.id == 123456
        assert event.workflow_run.name == "CI"
        assert event.workflow_run.status == "completed"
        assert event.workflow_run.conclusion == "success"
        assert event.repository.full_name == "owner/repo"
        assert event.sender.login == "user"


class TestWorkflowJobEvent:
    """Tests for WorkflowJobEvent model."""

    def test_parse_workflow_job_event(self) -> None:
        """Test parsing a workflow_job event payload."""
        payload = {
            "action": "completed",
            "workflow_job": {
                "id": 789012,
                "name": "build",
                "run_id": 123456,
                "workflow_name": "CI",
                "status": "completed",
                "conclusion": "success",
                "started_at": "2024-01-01T00:02:00Z",
                "completed_at": "2024-01-01T00:08:00Z",
                "html_url": "https://github.com/owner/repo/actions/runs/123456/jobs/789012",
                "runner_name": "runner-1",
                "runner_group_name": "Default",
                "labels": ["ubuntu-latest"],
            },
            "repository": {
                "id": 111,
                "name": "repo",
                "full_name": "owner/repo",
                "private": False,
                "html_url": "https://github.com/owner/repo",
            },
            "sender": {
                "id": 1,
                "login": "user",
                "type": "User",
            },
        }

        event = WorkflowJobEvent.model_validate(payload)
        assert event.action == "completed"
        assert event.workflow_job.id == 789012
        assert event.workflow_job.name == "build"
        assert event.workflow_job.status == "completed"
        assert event.workflow_job.runner_name == "runner-1"
        assert event.workflow_job.labels == ["ubuntu-latest"]


class TestWorkflowMetrics:
    """Tests for WorkflowMetrics model."""

    def test_create_workflow_metrics(self) -> None:
        """Test creating workflow metrics."""
        metrics = WorkflowMetrics(
            workflow_run_id=123456,
            workflow_id=789,
            workflow_name="CI",
            run_number=42,
            run_attempt=1,
            repository_id=111,
            repository_name="repo",
            repository_full_name="owner/repo",
            status="completed",
            conclusion="success",
            started_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            completed_at=datetime(2024, 1, 1, 0, 10, 0, tzinfo=UTC),
            duration_seconds=600.0,
            event_trigger="push",
            head_branch="main",
            head_sha="abc123",
            triggered_by="user",
            event_type="workflow_run",
            action="completed",
            processed_at=datetime.now(UTC),
        )
        assert metrics.duration_seconds == 600.0
        assert metrics.workflow_name == "CI"


class TestJobMetrics:
    """Tests for JobMetrics model."""

    def test_create_job_metrics_with_steps(self) -> None:
        """Test creating job metrics with steps."""
        steps = [
            Step(
                name="Checkout",
                status="completed",
                conclusion="success",
                number=1,
                started_at=datetime(2024, 1, 1, 0, 2, 0, tzinfo=UTC),
                completed_at=datetime(2024, 1, 1, 0, 2, 30, tzinfo=UTC),
            ),
            Step(
                name="Build",
                status="completed",
                conclusion="success",
                number=2,
                started_at=datetime(2024, 1, 1, 0, 2, 30, tzinfo=UTC),
                completed_at=datetime(2024, 1, 1, 0, 8, 0, tzinfo=UTC),
            ),
        ]

        metrics = JobMetrics(
            job_id=789012,
            job_name="build",
            workflow_run_id=123456,
            workflow_name="CI",
            repository_id=111,
            repository_name="repo",
            repository_full_name="owner/repo",
            status="completed",
            conclusion="success",
            started_at=datetime(2024, 1, 1, 0, 2, 0, tzinfo=UTC),
            completed_at=datetime(2024, 1, 1, 0, 8, 0, tzinfo=UTC),
            duration_seconds=360.0,
            runner_name="runner-1",
            labels=["ubuntu-latest"],
            event_type="workflow_job",
            action="completed",
            processed_at=datetime.now(UTC),
            steps=steps,
        )
        assert len(metrics.steps) == 2
        assert metrics.steps[0].name == "Checkout"
        assert metrics.duration_seconds == 360.0
