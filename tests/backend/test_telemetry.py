from datetime import UTC, datetime

from src.backend.telemetry import TelemetryClient
from src.shared.models import MetricValue


class TestTelemetryClient:
    def test_init_no_connection_string(self) -> None:
        """Test initialization without connection string."""
        client = TelemetryClient("")
        assert client._connection_string == ""
        assert client.exporter is None
        assert client.meter_provider is not None

    def test_init_with_connection_string(self) -> None:
        """Test initialization with a valid connection string."""
        # Use a valid dummy connection string format for testing
        client = TelemetryClient(
            "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )
        assert client._connection_string is not None
        assert client.exporter is not None
        assert client.meter_provider is not None

    def test_export_without_exporter(self) -> None:
        """Test export with no exporter configured."""
        client = TelemetryClient("")
        # Should not raise error even if exporter is None
        metrics = [
            MetricValue(
                name="test_metric",
                value=1.0,
                timestamp=datetime.now(UTC),
                attributes={"foo": "bar"},
            )
        ]
        client.export(metrics)

    def test_export_with_exporter(self) -> None:
        """Test export with exporter configured."""
        client = TelemetryClient(
            "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
            "IngestionEndpoint=https://test.applicationinsights.azure.com/"
        )
        metrics = [
            MetricValue(
                name="test_metric",
                value=42.5,
                timestamp=datetime.now(UTC),
                attributes={"repo": "test/repo"},
            )
        ]
        # Should not raise error
        client.export(metrics)
