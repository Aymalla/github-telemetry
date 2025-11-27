"""FastAPI application for receiving GitHub webhooks."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.frontend.config import FrontendSettings
from src.frontend.github_signature import validate_github_signature
from src.frontend.models import QueueMessage
from src.frontend.processor import EventProcessor
from src.frontend.telemetry import TelemetryClient, create_telemetry_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global settings and telemetry
settings = FrontendSettings()
telemetry_client: TelemetryClient | None = None
event_processor: EventProcessor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    global telemetry_client, event_processor

    logger.info("Starting webhook frontend service")

    if settings.applicationinsights_connection_string:
        telemetry_client = create_telemetry_client(settings.applicationinsights_connection_string)
        event_processor = EventProcessor(telemetry_client)
        logger.info("Application Insights telemetry initialized")
    else:
        logger.warning("No Application Insights connection string provided.")

    yield

    logger.info("Shutting down webhook frontend service")


app = FastAPI(
    title="GitHub Webhook Service",
    description="Receives GitHub webhooks and processes telemetry in real-time",
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

    # Process the event
    if event_processor:
        success = event_processor.process_message(
            QueueMessage(
                event_type=event_type,
                delivery_id=delivery_id,
                payload=payload,
                received_at=datetime.now(UTC),
            )
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process event",
            )
    else:
        logger.info(
            "Event logged (processor not configured): event=%s, delivery=%s",
            event_type,
            delivery_id,
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "message": "Event received and processed",
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
