"""Tests for Pydantic models."""

from datetime import UTC, datetime

from src.shared.models import (
    QueueMessage,
    WorkflowJobEvent,
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
