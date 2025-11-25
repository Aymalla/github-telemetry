"""Backend processor for GitHub webhook events."""

import logging
from datetime import UTC, datetime
from typing import Any

from src.backend.telemetry import TelemetryClient
from src.shared.models import (
    JobMetrics,
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
            if run.run_started_at and run.updated_at and run.status == "completed":
                duration = run.updated_at - run.run_started_at
                duration_seconds = duration.total_seconds()

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
                started_at=run.run_started_at,
                completed_at=run.updated_at if run.status == "completed" else None,
                duration_seconds=duration_seconds,
                event_trigger=run.event,
                head_branch=run.head_branch,
                head_sha=run.head_sha,
                triggered_by=event.sender.login,
                event_type=message.event_type,
                action=event.action,
                processed_at=datetime.now(UTC),
            )

            # Send telemetry
            self._send_workflow_telemetry(metrics)

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
            if job.started_at and job.completed_at:
                duration = job.completed_at - job.started_at
                duration_seconds = duration.total_seconds()

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
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=duration_seconds,
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

    def _send_workflow_telemetry(self, metrics: WorkflowMetrics) -> None:
        """Send workflow metrics to Application Insights.

        Args:
            metrics: Workflow metrics to send
        """
        properties = {
            "workflow_run_id": str(metrics.workflow_run_id),
            "workflow_id": str(metrics.workflow_id),
            "workflow_name": metrics.workflow_name,
            "run_number": str(metrics.run_number),
            "run_attempt": str(metrics.run_attempt),
            "repository_id": str(metrics.repository_id),
            "repository_name": metrics.repository_name,
            "repository_full_name": metrics.repository_full_name,
            "status": metrics.status,
            "conclusion": metrics.conclusion or "",
            "event_trigger": metrics.event_trigger,
            "head_branch": metrics.head_branch,
            "triggered_by": metrics.triggered_by,
            "action": metrics.action,
        }

        measurements: dict[str, float] = {}
        if metrics.duration_seconds is not None:
            measurements["duration_seconds"] = metrics.duration_seconds

        self._telemetry.track_workflow_event(
            name="WorkflowRun",
            properties=properties,
            measurements=measurements,
        )

        # Track duration as a separate metric for aggregation
        if metrics.duration_seconds is not None:
            self._telemetry.track_metric(
                name="workflow_duration_seconds",
                value=metrics.duration_seconds,
                properties={
                    "workflow_name": metrics.workflow_name,
                    "repository_full_name": metrics.repository_full_name,
                    "conclusion": metrics.conclusion or "",
                },
            )

    def _send_job_telemetry(self, metrics: JobMetrics) -> None:
        """Send job metrics to Application Insights with proper hierarchy.

        Args:
            metrics: Job metrics to send
        """
        properties = {
            "job_id": str(metrics.job_id),
            "job_name": metrics.job_name,
            "workflow_run_id": str(metrics.workflow_run_id),
            "workflow_name": metrics.workflow_name,
            "repository_id": str(metrics.repository_id),
            "repository_name": metrics.repository_name,
            "repository_full_name": metrics.repository_full_name,
            "status": metrics.status,
            "conclusion": metrics.conclusion or "",
            "runner_name": metrics.runner_name or "",
            "runner_group_name": metrics.runner_group_name or "",
            "labels": ",".join(metrics.labels),
            "action": metrics.action,
        }

        measurements: dict[str, float] = {}
        if metrics.duration_seconds is not None:
            measurements["duration_seconds"] = metrics.duration_seconds

        # Create a workflow span as parent
        workflow_span = self._telemetry.start_workflow_span(
            name=f"WorkflowRun {metrics.workflow_run_id}",
            workflow_run_id=str(metrics.workflow_run_id),
            properties={"workflow_run_id": str(metrics.workflow_run_id)},
        )

        # Create job span as child of workflow
        job_span = self._telemetry.start_child_span(
            name=f"WorkflowJob: {metrics.job_name}",
            parent_span=workflow_span,
            properties=properties,
            measurements=measurements,
        )

        # Track step metrics for completed jobs
        for step in metrics.steps:
            if step.started_at and step.completed_at:
                step_duration = (step.completed_at - step.started_at).total_seconds()

                # Send step as a child span of the job
                step_properties = {
                    "step_name": step.name,
                    "step_number": str(step.number),
                    "step_status": step.status,
                    "step_conclusion": step.conclusion or "",
                    "job_id": str(metrics.job_id),
                    "job_name": metrics.job_name,
                    "workflow_run_id": str(metrics.workflow_run_id),
                    "workflow_name": metrics.workflow_name,
                    "repository_id": str(metrics.repository_id),
                    "repository_name": metrics.repository_name,
                    "repository_full_name": metrics.repository_full_name,
                }

                step_measurements = {
                    "duration_seconds": step_duration,
                }

                step_span = self._telemetry.start_child_span(
                    name=f"WorkflowStep: {step.name}",
                    parent_span=job_span,
                    properties=step_properties,
                    measurements=step_measurements,
                )

                # End the step span
                self._telemetry.end_span(step_span)

                # Also track as a metric for backward compatibility and easier aggregation.
                # Metrics are better suited for statistical analysis (avg, sum, percentiles)
                # while events provide the full hierarchical context.
                self._telemetry.track_metric(
                    name="step_duration_seconds",
                    value=step_duration,
                    properties={
                        "step_name": step.name,
                        "step_number": str(step.number),
                        "job_id": str(metrics.job_id),
                        "job_name": metrics.job_name,
                        "workflow_run_id": str(metrics.workflow_run_id),
                        "workflow_name": metrics.workflow_name,
                        "repository_full_name": metrics.repository_full_name,
                        "conclusion": step.conclusion or "",
                    },
                )

        # End the job span
        self._telemetry.end_span(job_span)

        # End the workflow span
        self._telemetry.end_span(workflow_span)

        # Track duration as a separate metric for aggregation
        if metrics.duration_seconds is not None:
            self._telemetry.track_metric(
                name="job_duration_seconds",
                value=metrics.duration_seconds,
                properties={
                    "job_name": metrics.job_name,
                    "workflow_name": metrics.workflow_name,
                    "repository_full_name": metrics.repository_full_name,
                    "conclusion": metrics.conclusion or "",
                },
            )
