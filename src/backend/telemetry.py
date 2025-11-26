"""Azure Application Insights telemetry client."""

import logging
from typing import Any

from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.metrics_exporter import MetricsExporter
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace import execution_context
from opencensus.trace.samplers import AlwaysOnSampler
from opencensus.trace.span import SpanKind
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
        self._metrics_exporter = None

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

            # Set up metrics exporter
            self._metrics_exporter = MetricsExporter(connection_string=self._connection_string)
            logger.info("Application Insights telemetry initialized")
        except Exception as e:
            logger.error("Failed to initialize Application Insights: %s", str(e))

    def track_workflow_event(
        self,
        name: str,
        properties: dict[str, Any],
        measurements: dict[str, float] | None = None,
    ) -> None:
        """Track a workflow event.

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
        """Track a metric and export to Application Insights CustomMetrics table.

        Args:
            name: Metric name
            value: Metric value
            properties: Additional properties
        """
        properties = properties or {}

        # Export to Application Insights CustomMetrics table
        if self._metrics_exporter:
            self._metrics_exporter.export_metrics(
                [
                    {
                        "name": name,
                        "value": value,
                        "properties": properties,
                    }
                ]
            )

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
