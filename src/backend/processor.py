"""Backend processor for GitHub webhook events."""

import logging
from datetime import UTC, datetime
from typing import Any

from src.backend.telemetry import TelemetryClient
from src.shared.models import (
    JobMetrics,
    MetricValue,
    QueueMessage,
    WorkflowJobEvent,
    WorkflowMetrics,
    WorkflowRunEvent,
)

logger = logging.getLogger(__name__)


class EventProcessor:
    """Processes GitHub webhook events and generates telemetry."""

    def __init__(self, telemetry_client: TelemetryClient):
        """Initialize the event processor.

        Args:
            telemetry_client: Client for sending telemetry
        """
        self._telemetry = telemetry_client

    def process_message(self, message: QueueMessage) -> bool:
        """Process a queue message.

        Args:
            message: Queue message containing the event

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            event_type = message.event_type
            payload = message.payload

            if event_type == "workflow_run":
                return self._process_workflow_run(message, payload)
            elif event_type == "workflow_job":
                return self._process_workflow_job(message, payload)
            else:
                logger.warning("Unknown event type: %s", event_type)
                return True  # Don't retry unknown events

        except Exception as e:
            logger.error(
                "Failed to process message %s: %s",
                message.delivery_id,
                str(e),
            )
            return False

    def _process_workflow_run(self, message: QueueMessage, payload: dict[str, Any]) -> bool:
        """Process a workflow_run event.

        Args:
            message: Queue message
            payload: Event payload

        Returns:
            True if processed successfully
        """
        try:
            event = WorkflowRunEvent.model_validate(payload)
            run = event.workflow_run

            # Calculate duration if completed
            duration_seconds: float | None = None
            queue_duration_seconds: float | None = None
            if run.run_started_at and run.updated_at and run.status == "completed":
                duration = run.updated_at - run.run_started_at
                duration_seconds = duration.total_seconds()
                queue_duration_seconds = (run.run_started_at - run.created_at).total_seconds()

            # Create metrics
            metrics = WorkflowMetrics(
                workflow_run_id=run.id,
                workflow_id=run.workflow_id,
                workflow_name=run.name,
                run_number=run.run_number,
                run_attempt=run.run_attempt,
                repository_id=event.repository.id,
                repository_name=event.repository.name,
                repository_full_name=event.repository.full_name,
                status=run.status,
                conclusion=run.conclusion,
                created_at=run.created_at,
                started_at=run.run_started_at,
                completed_at=run.updated_at if run.status == "completed" else None,
                duration_seconds=duration_seconds,
                queue_duration_seconds=queue_duration_seconds,
                event_trigger=run.event,
                head_branch=run.head_branch,
                head_sha=run.head_sha,
                triggered_by=event.sender.login,
                event_type=message.event_type,
                action=event.action,
                processed_at=datetime.now(UTC),
            )

            # Send telemetry (only if duration is available)
            if metrics.duration_seconds is not None:
                self._telemetry.export(
                    [
                        MetricValue(
                            name="duration_seconds",
                            value=metrics.duration_seconds,
                            timestamp=metrics.processed_at,
                            attributes={
                                "type": "workflow_run",
                                "duration_seconds": str(metrics.duration_seconds),
                                "queue_duration_seconds": str(metrics.queue_duration_seconds),
                                "created_at": metrics.created_at,
                                "started_at": metrics.started_at,
                                "completed_at": metrics.completed_at,
                                "run_id": str(metrics.workflow_run_id),
                                "workflow_name": metrics.workflow_name,
                                "run_number": str(metrics.run_number),
                                "run_attempt": str(metrics.run_attempt),
                                "repository_id": str(metrics.repository_id),
                                "repository": metrics.repository_name,
                                "repository_full_name": metrics.repository_full_name,
                                "status": metrics.status,
                                "conclusion": metrics.conclusion or "",
                                "event_trigger": metrics.event_trigger,
                                "head_branch": metrics.head_branch,
                                "triggered_by": metrics.triggered_by,
                                "action": metrics.action,
                            },
                        )
                    ]
                )

            logger.info(
                "Processed workflow_run: %s/%s run #%d (%s)",
                event.repository.full_name,
                run.name,
                run.run_number,
                event.action,
            )
            return True

        except Exception as e:
            logger.error("Failed to process workflow_run: %s", str(e))
            return False

    def _process_workflow_job(self, message: QueueMessage, payload: dict[str, Any]) -> bool:
        """Process a workflow_job event.

        Args:
            message: Queue message
            payload: Event payload

        Returns:
            True if processed successfully
        """
        try:
            event = WorkflowJobEvent.model_validate(payload)
            job = event.workflow_job

            # Calculate duration if completed
            duration_seconds: float | None = None
            queue_duration_seconds: float | None = None
            if job.started_at and job.completed_at:
                duration = job.completed_at - job.started_at
                duration_seconds = duration.total_seconds()
                queue_duration_seconds = (job.started_at - job.created_at).total_seconds()

            # Create metrics using parsed data from the validated model
            metrics = JobMetrics(
                job_id=job.id,
                job_name=job.name,
                workflow_run_id=job.run_id,
                workflow_name=job.workflow_name,
                repository_id=event.repository.id,
                repository_name=event.repository.name,
                repository_full_name=event.repository.full_name,
                status=job.status,
                conclusion=job.conclusion,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=duration_seconds,
                queue_duration_seconds=queue_duration_seconds,
                runner_name=job.runner_name,
                runner_group_name=job.runner_group_name,
                labels=job.labels,
                event_type=message.event_type,
                action=event.action,
                processed_at=datetime.now(UTC),
                steps=job.steps,
            )

            # Send telemetry
            self._send_job_telemetry(metrics)

            logger.info(
                "Processed workflow_job: %s/%s (%s)",
                event.repository.full_name,
                job.name,
                event.action,
            )
            return True

        except Exception as e:
            logger.error("Failed to process workflow_job: %s", str(e))
            return False

    def _send_job_telemetry(self, metrics: JobMetrics) -> None:
        """Send job metrics to Application Insights.

        Args:
            metrics: Job metrics to send
        """

        # Track duration as a separate metric for aggregation
        if metrics.duration_seconds is not None:
            self._telemetry.export(
                [
                    MetricValue(
                        name="duration_seconds",
                        value=metrics.duration_seconds,
                        timestamp=metrics.processed_at,
                        attributes={
                            "type": "workflow_job",
                            "job_id": str(metrics.job_id),
                            "job_name": metrics.job_name,
                            "duration_seconds": str(metrics.duration_seconds),
                            "queue_duration_seconds": str(metrics.queue_duration_seconds),
                            "created_at": metrics.created_at,
                            "started_at": metrics.started_at,
                            "completed_at": metrics.completed_at,
                            "run_id": str(metrics.workflow_run_id),
                            "workflow_name": metrics.workflow_name,
                            "repository_id": str(metrics.repository_id),
                            "repository": metrics.repository_name,
                            "repository_full_name": metrics.repository_full_name,
                            "status": metrics.status,
                            "conclusion": metrics.conclusion or "",
                            "event_trigger": metrics.event_trigger,
                            "head_branch": metrics.head_branch,
                            "triggered_by": metrics.triggered_by,
                            "action": metrics.action,
                        },
                    )
                ]
            )

        # Track step metrics for completed jobs
        for step in metrics.steps:
            if step.started_at and step.completed_at:
                step_duration = (step.completed_at - step.started_at).total_seconds()
                self._telemetry.export(
                    [
                        MetricValue(
                            name="duration_seconds",
                            value=step_duration,
                            timestamp=metrics.processed_at,
                            attributes={
                                "type": "workflow_job_step",
                                "step_name": step.name,
                                "step_number": str(step.number),
                                "started_at": step.started_at,
                                "completed_at": step.completed_at,
                                "duration_seconds": str(step_duration),
                                "run_id": str(metrics.workflow_run_id),
                                "job_id": str(metrics.job_id),
                                "job_name": metrics.job_name,
                                "workflow_name": metrics.workflow_name,
                                "repository_id": str(metrics.repository_id),
                                "repository": metrics.repository_name,
                                "repository_full_name": metrics.repository_full_name,
                                "conclusion": step.conclusion or "",
                            },
                        )
                    ]
                )
