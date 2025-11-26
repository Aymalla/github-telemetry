# GitHub Telemetry

Captures GitHub workflow, job, and step telemetry using GitHub webhooks. The solution uses two Azure Container Apps: a Webhook Frontend that exposes an HTTPS endpoint, validates GitHub calls, and pushes events to an Azure Storage Queue; and a Webhook Backend that pulls queued events, processes workflow metrics (start/end/duration), enriches them, and sends telemetry to Azure Application Insights for monitoring and analysis.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   GitHub        │────▶│  Webhook         │────▶│  Azure Storage  │────▶│  Webhook         │
│   Webhooks      │     │  Frontend        │     │  Queue          │     │  Backend         │
│                 │     │  (Container App) │     │                 │     │  (Container App) │
└─────────────────┘     └──────────────────┘     └─────────────────┘     └──────────────────┘
                                                                                  │
                                                                                  ▼
                                                                         ┌──────────────────┐
                                                                         │  Azure App       │
                                                                         │  Insights        │
                                                                         └──────────────────┘
```

## Features

- **Webhook Frontend**: HTTPS endpoint for receiving GitHub webhooks
  - Validates GitHub webhook signatures (HMAC-SHA256)
  - Filters for `workflow_run` and `workflow_job` events
  - Queues events to Azure Storage Queue for reliable processing

- **Webhook Backend**: Background processor for telemetry generation
  - Polls Azure Storage Queue for new events
  - Processes workflow metrics (start time, end time, duration)
  - Enriches data with repository and runner information
  - Sends telemetry to Azure Application Insights

- **Telemetry Metrics**:
  - Workflow run duration
  - Job duration
  - Step duration
  - Success/failure rates
  - Runner utilization

## Prerequisites

- Python 3.11+
- Azure Storage Account with Queue service
- Azure Application Insights instance
- GitHub repository with webhook configured

## Installation

```bash
# Clone the repository
git clone https://github.com/Aymalla/github-telemetry.git
cd github-telemetry

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
make install-dev
```

## Configuration

### Frontend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Host to bind the server | `0.0.0.0` |
| `PORT` | Port to bind the server | `8080` |
| `GITHUB_WEBHOOK_SECRET` | GitHub webhook secret for signature validation | (empty) |
| `AZURE_STORAGE_ACCOUNT_NAME` | Azure Storage account name | (required) |
| `AZURE_STORAGE_QUEUE_NAME` | Name of the storage queue | `github-webhook-events` |

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_STORAGE_ACCOUNT_NAME` | Azure Storage account name | (required) |
| `AZURE_STORAGE_QUEUE_NAME` | Name of the storage queue | `github-webhook-events` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights connection string | (optional) |
| `POLL_INTERVAL_SECONDS` | Queue polling interval | `5` |
| `MAX_MESSAGES_PER_BATCH` | Max messages to process per batch | `32` |
| `VISIBILITY_TIMEOUT_SECONDS` | Message visibility timeout | `300` |

## Running Locally

### Frontend Service

```bash
# Set environment variables in .env file or export them
export AZURE_STORAGE_ACCOUNT_NAME="your-account-name"
export GITHUB_WEBHOOK_SECRET="your-webhook-secret"

# Run the frontend
make run-frontend
```

### Backend Service

```bash
# Set environment variables in .env file or export them
export AZURE_STORAGE_ACCOUNT_NAME="your-account-name"
export APPLICATIONINSIGHTS_CONNECTION_STRING="your-appinsights-connection-string"

# Run the backend
make run-backend
```

## Docker Deployment

### Build Images Locally

```bash
# Build frontend
make build-frontend

# Build backend
make build-backend

# Build both
make build
```

### Publish to Container Registry

```bash
# Set CONTAINER_REGISTRY in .env file
# Example: CONTAINER_REGISTRY=myregistry.azurecr.io

# Publish frontend
make publish-frontend

# Publish backend
make publish-backend

# Publish both
make publish
```

### Run Containers

```bash
# Run frontend
docker run -d \
  -e AZURE_STORAGE_ACCOUNT_NAME="..." \
  -e GITHUB_WEBHOOK_SECRET="..." \
  -p 8080:8080 \
  github-telemetry-frontend

# Run backend
docker run -d \
  -e AZURE_STORAGE_ACCOUNT_NAME="..." \
  -e APPLICATIONINSIGHTS_CONNECTION_STRING="..." \
  github-telemetry-backend
```

## GitHub Webhook Configuration

1. Go to your repository or organization settings
2. Navigate to **Webhooks** → **Add webhook**
3. Configure the webhook:
   - **Payload URL**: `https://your-frontend-url/webhook`
   - **Content type**: `application/json`
   - **Secret**: Your webhook secret (same as `FRONTEND_GITHUB_WEBHOOK_SECRET`)
   - **Events**: Select "Workflow runs" and "Workflow jobs"

## Development

### Quick Start with Make

```bash
# Show all available commands
make help

# Install development dependencies
make install-dev

# Run tests
make test

# Run tests with coverage
make test-cov

# Lint code
make lint

# Format code
make format

# Type check
make typecheck

# Clean build artifacts
make clean
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage report
make test-cov

# Run specific test file
pytest tests/shared/test_github_signature.py
```

### Code Quality

```bash
# Run linter
make lint

# Format code
make format

# Run type checking
make typecheck
```

### Testing GitHub Workflows

```bash
# Trigger 10 successful workflow test runs
make start-gh-workflows-success

# Trigger 10 failed workflow test runs
make start-gh-workflows-failures
```

## API Endpoints

### GET /health

Health check endpoint.

**Response**: `{"status": "healthy"}`

### POST /webhook

Receives GitHub webhook events.

**Headers**:
- `X-GitHub-Event`: Event type (e.g., `workflow_run`, `workflow_job`)
- `X-GitHub-Delivery`: Unique delivery ID
- `X-Hub-Signature-256`: HMAC-SHA256 signature

**Response**:
- `202 Accepted`: Event queued successfully
- `200 OK`: Event type not processed (ignored)
- `401 Unauthorized`: Invalid signature
- `400 Bad Request`: Invalid payload

## Telemetry Data

### Workflow Run Events

```json
{
  "name": "WorkflowRun",
  "properties": {
    "workflow_run_id": "123456",
    "workflow_name": "CI",
    "repository_full_name": "owner/repo",
    "status": "completed",
    "conclusion": "success",
    "triggered_by": "user"
  },
  "measurements": {
    "duration_seconds": 540.0
  }
}
```

### Workflow Job Events

```json
{
  "name": "WorkflowJob",
  "properties": {
    "job_id": "789012",
    "job_name": "build",
    "workflow_name": "CI",
    "repository_full_name": "owner/repo",
    "runner_name": "runner-1",
    "labels": "ubuntu-latest"
  },
  "measurements": {
    "duration_seconds": 360.0
  }
}
```

## License

MIT License - see [LICENSE](LICENSE) for details.