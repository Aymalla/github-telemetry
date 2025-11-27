"""Backend processor for GitHub webhook events."""

import logging
from datetime import UTC, datetime
from typing import Any

from src.frontend.models import (
    MetricValue,
    QueueMessage,
    WorkflowJobEvent,
    WorkflowRunEvent,
)
from src.frontend.telemetry import TelemetryClient

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
            if message.event_type == "workflow_run":
                return self._process_workflow_run(message.payload)
            elif message.event_type == "workflow_job":
                return self._process_workflow_job(message.payload)
            else:
                logger.warning("Unknown event type: %s", message.event_type)
                return True  # Don't retry unknown events

        except Exception as e:
            logger.error("Failed to process message: %s", str(e))
            return False

    def _process_workflow_run(self, payload: dict[str, Any]) -> bool:
        """Process a workflow_run event.

        Args:
            payload: Event payload

        Returns:
            True if processed successfully
        """
        try:
            event = WorkflowRunEvent.model_validate(payload)
            run = event.workflow_run

            # Calculate duration if completed
            if run.run_started_at and run.updated_at and run.status == "completed":
                completed_at: datetime = run.updated_at
                duration_seconds = (completed_at - run.run_started_at).total_seconds()
                queue_duration_seconds = (run.run_started_at - run.created_at).total_seconds()

                # Send telemetry for the workflow run
                self._telemetry.export(
                    [
                        MetricValue(
                            name="duration_seconds",
                            value=duration_seconds,
                            timestamp=datetime.now(UTC),
                            attributes={
                                "type": "workflow_run",
                                "duration_seconds": str(duration_seconds),
                                "queue_duration_seconds": str(queue_duration_seconds),
                                "created_at": run.created_at,
                                "started_at": run.run_started_at,
                                "completed_at": completed_at,
                                "run_id": str(run.id),
                                "workflow_name": run.name,
                                "run_number": str(run.run_number),
                                "run_attempt": str(run.run_attempt),
                                "repository_id": str(event.repository.id),
                                "repository": event.repository.name,
                                "repository_full_name": event.repository.full_name,
                                "status": run.status,
                                "conclusion": run.conclusion or "",
                                "event_trigger": run.event,
                                "head_branch": run.head_branch,
                                "triggered_by": event.sender.login,
                                "action": event.action,
                                "runner_name": run.runner_name or "",
                                "runner_group_name": run.runner_group_name or "",
                                "labels": run.labels,
                                "pool_name": self.get_mdp_name(run.labels),
                                "run_url": run.html_url,
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

    def _process_workflow_job(self, payload: dict[str, Any]) -> bool:
        """Process a workflow_job event.

        Args:
            payload: Event payload

        Returns:
            True if processed successfully
        """
        try:
            event = WorkflowJobEvent.model_validate(payload)
            job = event.workflow_job

            # Calculate duration if completed
            duration_seconds: float = 0
            queue_duration_seconds: float = 0
            if job.started_at and job.completed_at:
                duration = job.completed_at - job.started_at
                duration_seconds = duration.total_seconds()
                if job.created_at:
                    queue_duration_seconds = (job.started_at - job.created_at).total_seconds()

                # Create metrics using parsed data from the validated model

                # Send telemetry
                self._telemetry.export(
                    [
                        MetricValue(
                            name="duration_seconds",
                            value=duration_seconds,
                            timestamp=datetime.now(UTC),
                            attributes={
                                "type": "workflow_job",
                                "job_id": str(job.id),
                                "job_name": job.name,
                                "duration_seconds": str(duration_seconds),
                                "queue_duration_seconds": str(queue_duration_seconds),
                                "created_at": job.created_at,
                                "started_at": job.started_at,
                                "completed_at": job.completed_at,
                                "run_id": str(job.run_id),
                                "workflow_name": job.workflow_name,
                                "repository_id": str(event.repository.id),
                                "repository": event.repository.name,
                                "repository_full_name": event.repository.full_name,
                                "status": job.status,
                                "conclusion": job.conclusion or "",
                                "action": event.action,
                                "runner_name": job.runner_name or "",
                                "runner_group_name": job.runner_group_name or "",
                                "labels": job.labels,
                                "pool_name": self.get_mdp_name(job.labels),
                                "run_url": job.run_url,
                                "job_url": job.html_url,
                            },
                        )
                    ]
                )

            # Track step metrics for completed jobs
            for step in job.steps:
                if step.started_at and step.completed_at:
                    step_duration = (step.completed_at - step.started_at).total_seconds()
                    self._telemetry.export(
                        [
                            MetricValue(
                                name="duration_seconds",
                                value=step_duration,
                                timestamp=datetime.now(UTC),
                                attributes={
                                    "type": "workflow_job_step",
                                    "step_id": f"{job.id}-{step.number}",
                                    "step_name": step.name,
                                    "step_number": str(step.number),
                                    "started_at": step.started_at,
                                    "completed_at": step.completed_at,
                                    "duration_seconds": str(step_duration),
                                    "run_id": str(job.run_id),
                                    "parent_job_id": str(job.id),
                                    "parent_job_name": job.name,
                                    "job_id": str(job.id),
                                    "job_name": job.name,
                                    "workflow_name": job.workflow_name,
                                    "repository_id": str(event.repository.id),
                                    "repository": event.repository.name,
                                    "repository_full_name": event.repository.full_name,
                                    "conclusion": step.conclusion or "",
                                    "status": step.status,
                                    "run_url": job.run_url,
                                    "job_url": job.html_url,
                                },
                            )
                        ]
                    )

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

    def get_mdp_name(self, labels: list[str]) -> str:
        """Get the Managed DevOps pool name from the labels in case of runner using Azure Managed DevOps Pools.

        Args:
            labels (list[str]): List of labels from the workflow job.
        Returns:
            str: The Managed DevOps pool name if found, else an empty string.
        """

        pool_name = ""
        if labels:
            for value in labels:
                if "ManagedDevOps.Pool=" in value:
                    pool_name = value.split("ManagedDevOps.Pool=")[1]
                    break
        return pool_name
