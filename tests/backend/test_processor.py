"""Tests for the backend event processor."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.shared.models import QueueMessage
from src.shared.processor import EventProcessor
from src.shared.telemetry import TelemetryClient


@pytest.fixture
def mock_telemetry() -> MagicMock:
    """Create a mock telemetry client."""
    mock = MagicMock(spec=TelemetryClient)
    mock.export = MagicMock()
    return mock


@pytest.fixture
def processor(mock_telemetry: MagicMock) -> EventProcessor:
    """Create an event processor with mocked telemetry."""
    return EventProcessor(mock_telemetry)


@pytest.fixture
def workflow_run_message() -> QueueMessage:
    """Create a sample workflow_run queue message."""
    return QueueMessage(
        event_type="workflow_run",
        delivery_id="test-delivery-123",
        received_at=datetime.now(UTC),
        payload={
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
        },
    )


@pytest.fixture
def workflow_job_message() -> QueueMessage:
    """Create a sample workflow_job queue message."""
    return QueueMessage(
        event_type="workflow_job",
        delivery_id="test-delivery-456",
        received_at=datetime.now(UTC),
        payload={
            "action": "completed",
            "workflow_job": {
                "id": 789012,
                "name": "build",
                "run_id": 123456,
                "workflow_name": "CI",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2024-01-01T00:02:00Z",
                "started_at": "2024-01-01T00:02:00Z",
                "completed_at": "2024-01-01T00:08:00Z",
                "html_url": "https://github.com/owner/repo/actions/runs/123456/jobs/789012",
                "runner_name": "runner-1",
                "runner_group_name": "Default",
                "labels": ["ubuntu-latest"],
                "steps": [
                    {
                        "name": "Checkout",
                        "status": "completed",
                        "conclusion": "success",
                        "number": 1,
                        "started_at": "2024-01-01T00:02:00Z",
                        "completed_at": "2024-01-01T00:02:30Z",
                    },
                    {
                        "name": "Build",
                        "status": "completed",
                        "conclusion": "success",
                        "number": 2,
                        "started_at": "2024-01-01T00:02:30Z",
                        "completed_at": "2024-01-01T00:08:00Z",
                    },
                ],
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
        },
    )


class TestEventProcessor:
    """Tests for EventProcessor class."""

    def test_process_workflow_run(
        self,
        processor: EventProcessor,
        workflow_run_message: QueueMessage,
        mock_telemetry: MagicMock,
    ) -> None:
        """Test processing a workflow_run event."""
        result = processor.process_message(workflow_run_message)
        assert result is True

        # Verify telemetry was sent via export
        assert mock_telemetry.export.called
        call_args = mock_telemetry.export.call_args
        metrics = call_args[0][0]  # First positional arg is the metrics list
        assert len(metrics) > 0
        # Check that metrics were exported (duration_seconds for workflows)
        metric_names = [m.name for m in metrics]
        assert "duration_seconds" in metric_names

    def test_process_workflow_run_calculates_duration(
        self,
        processor: EventProcessor,
        workflow_run_message: QueueMessage,
        mock_telemetry: MagicMock,
    ) -> None:
        """Test that duration is calculated for completed workflows."""
        result = processor.process_message(workflow_run_message)
        assert result is True

        # Verify export was called with metrics
        assert mock_telemetry.export.called
        call_args = mock_telemetry.export.call_args
        metrics = call_args[0][0]
        # Check for duration metric
        duration_metrics = [m for m in metrics if "duration" in m.name.lower()]
        assert len(duration_metrics) > 0
        # Duration should be 9 minutes = 540 seconds (10:00 - 01:00)
        assert any(m.value == 540.0 for m in duration_metrics)

    def test_process_workflow_job(
        self,
        processor: EventProcessor,
        workflow_job_message: QueueMessage,
        mock_telemetry: MagicMock,
    ) -> None:
        """Test processing a workflow_job event."""
        result = processor.process_message(workflow_job_message)
        assert result is True

        # Verify telemetry was sent via export
        assert mock_telemetry.export.called
        call_args = mock_telemetry.export.call_args
        metrics = call_args[0][0]
        assert len(metrics) > 0
        # Check that job metrics were exported (duration_seconds for jobs)
        metric_names = [m.name for m in metrics]
        assert "duration_seconds" in metric_names

    def test_process_workflow_job_tracks_step_metrics(
        self,
        processor: EventProcessor,
        workflow_job_message: QueueMessage,
        mock_telemetry: MagicMock,
    ) -> None:
        """Test that step metrics are tracked for completed jobs."""
        result = processor.process_message(workflow_job_message)
        assert result is True

        # Export should be called multiple times: one for job duration + one per step
        assert mock_telemetry.export.call_count >= 3

    def test_process_unknown_event(
        self, processor: EventProcessor, mock_telemetry: MagicMock
    ) -> None:
        """Test processing an unknown event type."""
        message = QueueMessage(
            event_type="unknown_event",
            delivery_id="test-delivery-789",
            received_at=datetime.now(UTC),
            payload={"action": "test"},
        )
        result = processor.process_message(message)
        # Unknown events are skipped, not retried
        assert result is True
        assert not mock_telemetry.export.called

    def test_process_in_progress_workflow(
        self, processor: EventProcessor, mock_telemetry: MagicMock
    ) -> None:
        """Test processing an in_progress workflow_run event."""
        message = QueueMessage(
            event_type="workflow_run",
            delivery_id="test-delivery-in-progress",
            received_at=datetime.now(UTC),
            payload={
                "action": "in_progress",
                "workflow_run": {
                    "id": 123456,
                    "name": "CI",
                    "workflow_id": 789,
                    "head_branch": "main",
                    "head_sha": "abc123",
                    "status": "in_progress",
                    "conclusion": None,
                    "run_number": 42,
                    "run_attempt": 1,
                    "event": "push",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:01:00Z",
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
            },
        )
        result = processor.process_message(message)
        assert result is True

        # In-progress workflow should not export duration metric
        assert mock_telemetry.export.call_count == 0
