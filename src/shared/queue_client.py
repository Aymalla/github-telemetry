"""Azure Storage Queue client utilities."""

import base64
import logging
from datetime import UTC, datetime
from typing import Any

from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.queue import QueueClient
from azure.storage.queue import QueueMessage as AzureQueueMessage

from src.shared.models import QueueMessage

logger = logging.getLogger(__name__)


class QueueClientWrapper:
    """Wrapper for Azure Storage Queue operations."""

    def __init__(self, account_name: str, queue_name: str):
        """Initialize the queue client.

        Args:
            account_name: Azure Storage account name
            queue_name: Name of the queue
        """
        # Derive account name from a connection string if provided; otherwise treat the
        # value as the account name directly. Use DefaultAzureCredential for auth instead
        # of embedding secrets in a connection string.
        account_url = f"https://{account_name}.queue.core.windows.net"
        self._queue_client = QueueClient(
            account_url=account_url,
            queue_name=queue_name,
            credential=DefaultAzureCredential(),
        )
        self._queue_name = queue_name

    def ensure_queue_exists(self) -> None:
        """Create the queue if it doesn't exist."""
        try:
            self._queue_client.create_queue()
            logger.info("Queue '%s' created successfully", self._queue_name)
        except AzureError as e:
            # Queue already exists is not an error
            if "QueueAlreadyExists" not in str(e):
                logger.warning("Queue creation response: %s", str(e))

    def send_message(
        self,
        event_type: str,
        delivery_id: str,
        payload: dict[str, Any],
    ) -> bool:
        """Send a message to the queue.

        Args:
            event_type: Type of the GitHub event
            delivery_id: GitHub delivery ID
            payload: Event payload

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            message = QueueMessage(
                event_type=event_type,
                delivery_id=delivery_id,
                received_at=datetime.now(UTC),
                payload=payload,
            )
            # Encode message content as base64 for Azure Queue
            message_content = base64.b64encode(message.model_dump_json().encode("utf-8")).decode(
                "utf-8"
            )
            self._queue_client.send_message(message_content)
            logger.info(
                "Message sent to queue: event_type=%s, delivery_id=%s",
                event_type,
                delivery_id,
            )
            return True
        except AzureError as e:
            logger.error("Failed to send message to queue: %s", str(e))
            return False

    def receive_messages(
        self,
        max_messages: int = 32,
        visibility_timeout: int = 300,
    ) -> list[tuple[AzureQueueMessage, QueueMessage]]:
        """Receive messages from the queue.

        Args:
            max_messages: Maximum number of messages to receive
            visibility_timeout: Visibility timeout in seconds

        Returns:
            List of tuples containing (Azure message, parsed QueueMessage)
        """
        messages: list[tuple[AzureQueueMessage, QueueMessage]] = []
        try:
            azure_messages = self._queue_client.receive_messages(
                max_messages=max_messages,
                visibility_timeout=visibility_timeout,
            )
            for azure_msg in azure_messages:
                try:
                    # Decode base64 content
                    content = base64.b64decode(azure_msg.content).decode("utf-8")
                    queue_message = QueueMessage.model_validate_json(content)
                    messages.append((azure_msg, queue_message))
                except Exception as e:
                    logger.error("Failed to parse queue message: %s", str(e))
                    # Delete malformed messages
                    self.delete_message(azure_msg)
        except AzureError as e:
            logger.error("Failed to receive messages from queue: %s", str(e))
        return messages

    def delete_message(self, message: AzureQueueMessage) -> bool:
        """Delete a message from the queue.

        Args:
            message: Azure queue message to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self._queue_client.delete_message(message)
            return True
        except AzureError as e:
            logger.error("Failed to delete message: %s", str(e))
            return False


def create_queue_client(account_name: str, queue_name: str) -> QueueClientWrapper:
    """Create a queue client wrapper.

    Args:
        account_name: Azure Storage account name
        queue_name: Name of the queue

    Returns:
        QueueClientWrapper instance
    """
    client = QueueClientWrapper(account_name, queue_name)
    client.ensure_queue_exists()
    return client
