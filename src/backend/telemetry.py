"""Azure Application Insights telemetry client."""

import logging
from typing import Any

from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace import execution_context
from opencensus.trace.samplers import AlwaysOnSampler
from opencensus.trace.span import Span, SpanKind
from opencensus.trace.span_context import SpanContext
from opencensus.trace.tracer import Tracer

logger = logging.getLogger(__name__)


class TelemetryClient:
    """Client for sending telemetry to Azure Application Insights."""

    def __init__(self, connection_string: str):
        """Initialize the telemetry client.

        Args:
            connection_string: Application Insights connection string
        """
        self._connection_string = connection_string
        self._tracer: Tracer | None = None
        self._logger: logging.Logger | None = None

        if connection_string:
            self._setup_telemetry()
        else:
            logger.warning(
                "No Application Insights connection string provided. "
                "Telemetry will be logged locally only."
            )

    def _setup_telemetry(self) -> None:
        """Set up Application Insights exporters."""
        try:
            # Set up trace exporter
            exporter = AzureExporter(connection_string=self._connection_string)
            self._tracer = Tracer(
                exporter=exporter,
                sampler=AlwaysOnSampler(),
            )

            # Set up log handler
            self._logger = logging.getLogger("telemetry")
            self._logger.setLevel(logging.INFO)

            # Add Azure handler if not already present
            if not any(isinstance(h, AzureLogHandler) for h in self._logger.handlers):
                azure_handler = AzureLogHandler(connection_string=self._connection_string)
                self._logger.addHandler(azure_handler)

            logger.info("Application Insights telemetry initialized")
        except Exception as e:
            logger.error("Failed to initialize Application Insights: %s", str(e))

    def start_workflow_span(
        self,
        name: str,
        workflow_run_id: str,
        properties: dict[str, Any],
        measurements: dict[str, float] | None = None,
    ) -> Span | None:
        """Start a workflow span that will be the parent for job spans.

        Args:
            name: Span name
            workflow_run_id: Workflow run ID to use as trace_id
            properties: Span properties
            measurements: Numeric measurements

        Returns:
            The created span or None if tracer not available
        """
        measurements = measurements or {}

        if self._tracer:
            # Create a span context with workflow_run_id as the trace_id
            # This ensures all related spans share the same operation_id
            span_context = SpanContext(trace_id=self._generate_trace_id(workflow_run_id))
            span = self._tracer.start_span(name=name)
            span.span_kind = SpanKind.SERVER
            span.context_tracer.span_context = span_context

            for key, value in properties.items():
                span.add_attribute(key, str(value))
            for key, value in measurements.items():
                span.add_attribute(key, value)

            return span

        if self._logger:
            self._logger.info(
                "%s: %s",
                name,
                {**properties, **measurements},
                extra={"custom_dimensions": {**properties, **measurements}},
            )
        else:
            logger.info(
                "Event: %s, Properties: %s, Measurements: %s", name, properties, measurements
            )

        return None

    def start_child_span(
        self,
        name: str,
        parent_span: Span | None,
        properties: dict[str, Any],
        measurements: dict[str, float] | None = None,
    ) -> Span | None:
        """Start a child span under a parent span.

        Args:
            name: Span name
            parent_span: Parent span
            properties: Span properties
            measurements: Numeric measurements

        Returns:
            The created span or None if tracer not available
        """
        measurements = measurements or {}

        if self._tracer and parent_span:
            # Create child span with parent reference
            child_span = Span(
                name=name,
                parent_span=parent_span,
                context_tracer=parent_span.context_tracer,
            )
            child_span.span_kind = SpanKind.INTERNAL

            for key, value in properties.items():
                child_span.add_attribute(key, str(value))
            for key, value in measurements.items():
                child_span.add_attribute(key, value)

            # Start the span
            child_span.start()
            return child_span

        if self._logger:
            self._logger.info(
                "%s: %s",
                name,
                {**properties, **measurements},
                extra={"custom_dimensions": {**properties, **measurements}},
            )
        else:
            logger.info(
                "Event: %s, Properties: %s, Measurements: %s", name, properties, measurements
            )

        return None

    def end_span(self, span: Span | None) -> None:
        """End a span and export it.

        Args:
            span: Span to end
        """
        if span:
            span.finish()
            if self._tracer:
                self._tracer.exporter.export([span])

    def _generate_trace_id(self, workflow_run_id: str) -> str:
        """Generate a trace ID from workflow_run_id.

        Args:
            workflow_run_id: Workflow run ID

        Returns:
            32-character hex trace ID
        """
        import hashlib

        # Generate a consistent 32-character hex string from workflow_run_id
        hash_obj = hashlib.sha256(str(workflow_run_id).encode())
        return hash_obj.hexdigest()[:32]

    def track_workflow_event(
        self,
        name: str,
        properties: dict[str, Any],
        measurements: dict[str, float] | None = None,
    ) -> None:
        """Track a workflow event (legacy method for backward compatibility).

        Args:
            name: Event name
            properties: Event properties
            measurements: Numeric measurements
        """
        measurements = measurements or {}

        if self._tracer:
            with self._tracer.span(name=name) as span:
                span.span_kind = SpanKind.SERVER
                for key, value in properties.items():
                    span.add_attribute(key, str(value))
                for key, value in measurements.items():
                    span.add_attribute(key, value)

        if self._logger:
            self._logger.info(
                "%s: %s",
                name,
                {**properties, **measurements},
                extra={"custom_dimensions": {**properties, **measurements}},
            )
        else:
            logger.info(
                "Event: %s, Properties: %s, Measurements: %s", name, properties, measurements
            )

    def track_metric(
        self,
        name: str,
        value: float,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Track a metric.

        Args:
            name: Metric name
            value: Metric value
            properties: Additional properties
        """
        properties = properties or {}

        if self._logger:
            self._logger.info(
                "Metric: %s = %s",
                name,
                value,
                extra={"custom_dimensions": {"metric_name": name, "value": value, **properties}},
            )
        else:
            logger.info("Metric: %s = %s, Properties: %s", name, value, properties)

    def flush(self) -> None:
        """Flush any pending telemetry."""
        if self._tracer:
            tracer = execution_context.get_opencensus_tracer()
            if tracer:
                tracer.finish()


def create_telemetry_client(connection_string: str) -> TelemetryClient:
    """Create a telemetry client.

    Args:
        connection_string: Application Insights connection string

    Returns:
        TelemetryClient instance
    """
    return TelemetryClient(connection_string)
