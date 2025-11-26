"""Backend service for processing GitHub webhook events from the queue."""

import logging
import signal
import time
from types import FrameType

from src.backend.processor import EventProcessor
from src.backend.telemetry import create_telemetry_client
from src.shared.config import BackendSettings
from src.shared.queue_client import create_queue_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class BackendService:
    """Background service for processing webhook events."""

    def __init__(self, settings: BackendSettings):
        """Initialize the backend service.

        Args:
            settings: Backend configuration settings
        """
        self._settings = settings
        self._running = False
        self._queue_client = create_queue_client(
            settings.azure_storage_account_name,
            settings.azure_storage_queue_name,
        )
        self._telemetry_client = create_telemetry_client(
            settings.applicationinsights_connection_string
        )
        self._processor = EventProcessor(self._telemetry_client)

    def start(self) -> None:
        """Start the background processing loop."""
        self._running = True
        logger.info("Starting backend service")

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        while self._running:
            try:
                self._process_messages()
            except Exception as e:
                logger.error("Error in processing loop: %s", str(e))

            # Wait before next poll
            time.sleep(self._settings.poll_interval_seconds)

        # telemetry before shutdown
        logger.info("Backend service stopped")

    def stop(self) -> None:
        """Stop the background processing loop."""
        logger.info("Stopping backend service")
        self._running = False

    def _handle_signal(self, signum: int, frame: FrameType | None) -> None:
        """Handle shutdown signals.

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info("Received signal %s, shutting down", signum)
        self.stop()

    def _process_messages(self) -> None:
        """Process messages from the queue."""
        messages = self._queue_client.receive_messages(
            max_messages=self._settings.max_messages_per_batch,
            visibility_timeout=self._settings.visibility_timeout_seconds,
        )

        if not messages:
            logger.debug("No messages to process")
            return

        logger.info("Processing %d messages", len(messages))

        for azure_msg, queue_msg in messages:
            try:
                success = self._processor.process_message(queue_msg)
                if success:
                    self._queue_client.delete_message(azure_msg)
                    logger.debug("Message processed and deleted: %s", queue_msg.delivery_id)
                else:
                    logger.warning(
                        "Message processing failed, will retry: %s",
                        queue_msg.delivery_id,
                    )
            except Exception as e:
                logger.error(
                    "Error processing message %s: %s",
                    queue_msg.delivery_id,
                    str(e),
                )


def main() -> None:
    """Main entry point for the backend service."""
    settings = BackendSettings()

    if not settings.azure_storage_account_name:
        logger.error("Azure Storage account name is required")
        return

    service = BackendService(settings)
    service.start()


if __name__ == "__main__":
    main()
