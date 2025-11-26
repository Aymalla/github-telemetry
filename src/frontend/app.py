"""FastAPI application for receiving GitHub webhooks."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.shared.config import FrontendSettings
from src.shared.github_signature import validate_github_signature
from src.shared.queue_client import QueueClientWrapper, create_queue_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global settings and queue client
settings = FrontendSettings()
queue_client: QueueClientWrapper | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    global queue_client

    logger.info("Starting webhook frontend service")

    # Initialize queue client if account name is provided
    if settings.azure_storage_account_name:
        queue_client = create_queue_client(
            settings.azure_storage_account_name,
            settings.azure_storage_queue_name,
        )
        logger.info("Queue client initialized")
    else:
        logger.warning(
            "No Azure Storage account name provided. Events will be logged but not queued."
        )

    yield

    logger.info("Shutting down webhook frontend service")


app = FastAPI(
    title="GitHub Webhook Frontend",
    description="Receives GitHub webhooks and queues them for processing",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> JSONResponse:
    """Receive and process GitHub webhooks.

    This endpoint:
    1. Validates the webhook signature
    2. Parses the event payload
    3. Queues relevant events for processing
    """
    # Read raw body for signature validation
    body = await request.body()

    # Validate signature
    if not validate_github_signature(
        payload=body,
        signature_header=x_hub_signature_256,
        secret=settings.github_webhook_secret,
    ):
        logger.warning("Invalid webhook signature for delivery %s", x_github_delivery)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Parse payload
    try:
        payload: dict[str, Any] = await request.json()
    except Exception as e:
        logger.error("Failed to parse webhook payload: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from None

    event_type = x_github_event or "unknown"
    delivery_id = x_github_delivery or "unknown"

    logger.info(
        "Received webhook: event=%s, delivery=%s, action=%s",
        event_type,
        delivery_id,
        payload.get("action", "N/A"),
    )

    # Only process workflow_run and workflow_job events
    if event_type not in ("workflow_run", "workflow_job"):
        logger.debug("Ignoring event type: %s", event_type)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Event type not processed", "event": event_type},
        )

    # Queue the event for processing
    if queue_client:
        success = queue_client.send_message(
            event_type=event_type,
            delivery_id=delivery_id,
            payload=payload,
        )
        if not success:
            logger.error("Failed to queue event: %s", delivery_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to queue event",
            )
    else:
        logger.info("Event logged (queue not configured): %s", payload)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "message": "Event received and queued",
            "event": event_type,
            "delivery": delivery_id,
        },
    )


def create_app() -> FastAPI:
    """Create the FastAPI application.

    This factory function is useful for testing.
    """
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.frontend.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
