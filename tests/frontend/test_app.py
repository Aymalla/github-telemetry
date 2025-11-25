"""Tests for the frontend webhook endpoint."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.frontend.app import app, settings
from tests.conftest import compute_signature


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def workflow_run_payload() -> dict:
    """Create a sample workflow_run event payload."""
    return {
        "action": "completed",
        "workflow_run": {
            "id": 123456,
            "name": "CI",
            "workflow_id": 789,
            "head_branch": "main",
            "head_sha": "abc123",
            "status": "completed",
            "conclusion": "success",
            "run_number": 42,
            "run_attempt": 1,
            "event": "push",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:10:00Z",
            "run_started_at": "2024-01-01T00:01:00Z",
            "html_url": "https://github.com/owner/repo/actions/runs/123456",
        },
        "repository": {
            "id": 111,
            "name": "repo",
            "full_name": "owner/repo",
            "private": False,
            "html_url": "https://github.com/owner/repo",
        },
        "sender": {
            "id": 1,
            "login": "user",
            "type": "User",
        },
    }


@pytest.fixture
def workflow_job_payload() -> dict:
    """Create a sample workflow_job event payload."""
    return {
        "action": "completed",
        "workflow_job": {
            "id": 789012,
            "name": "build",
            "run_id": 123456,
            "workflow_name": "CI",
            "status": "completed",
            "conclusion": "success",
            "started_at": "2024-01-01T00:02:00Z",
            "completed_at": "2024-01-01T00:08:00Z",
            "html_url": "https://github.com/owner/repo/actions/runs/123456/jobs/789012",
            "runner_name": "runner-1",
            "runner_group_name": "Default",
            "labels": ["ubuntu-latest"],
            "steps": [
                {
                    "name": "Checkout",
                    "status": "completed",
                    "conclusion": "success",
                    "number": 1,
                    "started_at": "2024-01-01T00:02:00Z",
                    "completed_at": "2024-01-01T00:02:30Z",
                }
            ],
        },
        "repository": {
            "id": 111,
            "name": "repo",
            "full_name": "owner/repo",
            "private": False,
            "html_url": "https://github.com/owner/repo",
        },
        "sender": {
            "id": 1,
            "login": "user",
            "type": "User",
        },
    }


class TestHealthCheck:
    """Tests for the health check endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test that health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestWebhook:
    """Tests for the webhook endpoint."""

    def test_webhook_workflow_run_without_signature(
        self, client: TestClient, workflow_run_payload: dict
    ) -> None:
        """Test webhook accepts workflow_run when no secret is configured."""
        # When no secret is configured, signature validation is skipped
        with patch.object(settings, "github_webhook_secret", ""):
            response = client.post(
                "/webhook",
                json=workflow_run_payload,
                headers={
                    "X-GitHub-Event": "workflow_run",
                    "X-GitHub-Delivery": "test-delivery-123",
                },
            )
        assert response.status_code == 202
        data = response.json()
        assert data["event"] == "workflow_run"

    def test_webhook_rejects_invalid_signature(
        self, client: TestClient, workflow_run_payload: dict
    ) -> None:
        """Test webhook rejects invalid signature."""
        with patch.object(settings, "github_webhook_secret", "test-secret"):
            response = client.post(
                "/webhook",
                json=workflow_run_payload,
                headers={
                    "X-GitHub-Event": "workflow_run",
                    "X-GitHub-Delivery": "test-delivery-123",
                    "X-Hub-Signature-256": "sha256=invalid",
                },
            )
        assert response.status_code == 401

    def test_webhook_accepts_valid_signature(
        self, client: TestClient, workflow_run_payload: dict
    ) -> None:
        """Test webhook accepts valid signature."""
        secret = "test-secret"
        payload_bytes = json.dumps(workflow_run_payload).encode("utf-8")
        signature = compute_signature(payload_bytes, secret)

        with patch.object(settings, "github_webhook_secret", secret):
            response = client.post(
                "/webhook",
                content=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "workflow_run",
                    "X-GitHub-Delivery": "test-delivery-123",
                    "X-Hub-Signature-256": signature,
                },
            )
        assert response.status_code == 202

    def test_webhook_ignores_irrelevant_events(self, client: TestClient) -> None:
        """Test webhook ignores non-workflow events."""
        with patch.object(settings, "github_webhook_secret", ""):
            response = client.post(
                "/webhook",
                json={"action": "opened"},
                headers={
                    "X-GitHub-Event": "issues",
                    "X-GitHub-Delivery": "test-delivery-123",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Event type not processed"

    def test_webhook_workflow_job(self, client: TestClient, workflow_job_payload: dict) -> None:
        """Test webhook accepts workflow_job events."""
        with patch.object(settings, "github_webhook_secret", ""):
            response = client.post(
                "/webhook",
                json=workflow_job_payload,
                headers={
                    "X-GitHub-Event": "workflow_job",
                    "X-GitHub-Delivery": "test-delivery-456",
                },
            )
        assert response.status_code == 202
        data = response.json()
        assert data["event"] == "workflow_job"

    def test_webhook_invalid_json(self, client: TestClient) -> None:
        """Test webhook rejects invalid JSON."""
        with patch.object(settings, "github_webhook_secret", ""):
            response = client.post(
                "/webhook",
                content=b"not json",
                headers={
                    "Content-Type": "application/json",
                    "X-GitHub-Event": "workflow_run",
                    "X-GitHub-Delivery": "test-delivery-789",
                },
            )
        assert response.status_code == 400
