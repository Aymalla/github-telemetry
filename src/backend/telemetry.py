"""Azure Application Insights telemetry client using azure-monitor-opentelemetry."""

import logging
from datetime import datetime

from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
from opentelemetry import metrics
from opentelemetry.sdk.metrics.export import (
    Gauge,
    Metric,
    MetricsData,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.util.instrumentation import InstrumentationScope

from src.shared.models import MetricValue

logger = logging.getLogger(__name__)


class TelemetryClient:
    """Client for sending telemetry to Azure Application Insights using azure-monitor-opentelemetry."""

    def __init__(self, connection_string: str):
        self._connection_string = connection_string
        self.exporter = None
        self.meter_provider = metrics.get_meter_provider()

        if connection_string:
            try:
                self.exporter = AzureMonitorMetricExporter(connection_string=connection_string)
                logger.info("Application Insights telemetry initialized")
            except Exception as e:
                logger.error("Failed to initialize Application Insights: %s", str(e))
        else:
            logger.warning(
                "No Application Insights connection string provided. "
                "Telemetry will be logged locally only."
            )

    def export(self, metrics_data: list[MetricValue]) -> None:
        """Export metrics to Azure Monitor
        Args:
            metrics_data (list[MetricValue]): List of MetricValue objects to be exported.
        """
        if not self.exporter:
            logger.debug("No exporter configured, skipping metric export")
            return

        azure_monitor_metrics: list[ResourceMetrics] = []
        for metric in metrics_data:
            attributes = metric.attributes or {}
            # Ensure all attribute values are strings
            attributes = {str(k): str(v) for k, v in attributes.items()}

            exported_metric = Metric(
                name=metric.name,
                description=metric.name,
                unit="1",
                data=Gauge(
                    [
                        NumberDataPoint(
                            attributes=attributes,
                            start_time_unix_nano=self.to_ns_time_value(metric.timestamp),
                            time_unix_nano=self.to_ns_time_value(metric.timestamp),
                            value=metric.value,
                            exemplars=[],
                        )
                    ]
                ),
            )

            azure_monitor_metrics.append(
                ResourceMetrics(
                    resource=Resource.create(
                        {
                            "service.namespace": "nokia",
                            "service.name": "metrics-processor",
                            "cloud.role": "metrics-processor",
                        }
                    ),
                    scope_metrics=[
                        ScopeMetrics(
                            scope=InstrumentationScope(name="gh-job", version="1.0.0"),
                            metrics=[exported_metric],
                            schema_url="",
                        )
                    ],
                    schema_url="",
                )
            )

        self.exporter.export(MetricsData(resource_metrics=azure_monitor_metrics))

    def to_ns_time_value(self, dt: datetime) -> int:
        return int(dt.timestamp() * 1e9)


def create_telemetry_client(connection_string: str) -> TelemetryClient:
    """Create a telemetry client.

    Args:
        connection_string: Application Insights connection string

    Returns:
        TelemetryClient instance
    """
    return TelemetryClient(connection_string)
