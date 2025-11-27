# GitHub Telemetry

Captures GitHub workflow, job, and step telemetry using GitHub webhooks. The solution uses an Azure Container App that exposes an HTTPS endpoint, validates GitHub webhook signatures, processes workflow metrics (start/end/duration), enriches them with repository and runner information, and sends telemetry directly to Azure Application Insights for monitoring and analysis.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   GitHub        │────▶│  Webhook         │────▶│  Azure App       │
│   Webhooks      │     │  Frontend        │     │  Insights        │
│                 │     │  (Container App) │     │                  │
└─────────────────┘     └──────────────────┘     └──────────────────┘
```

## Features

- **Webhook Service**: HTTPS endpoint for receiving and processing GitHub webhooks
  - Validates GitHub webhook signatures (HMAC-SHA256)
  - Filters for `workflow_run` and `workflow_job` events
  - Processes workflow metrics (start time, end time, duration) in real-time
  - Enriches data with repository and runner information
  - Sends telemetry directly to Azure Application Insights

- **Telemetry Metrics**:
  - Workflow run duration
  - Job duration
  - Step duration
  - Success/failure rates
  - Runner utilization

## Prerequisites

- Python 3.11+
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

```bash
# Set environment variables in .env file or export them
export GITHUB_WEBHOOK_SECRET="your-webhook-secret"
export APPLICATIONINSIGHTS_CONNECTION_STRING="your-appinsights-connection-string"

# Run the service
make run-frontend
```

## Docker Deployment

### Build Image Locally

```bash
make build-frontend
```

### Publish to Container Registry

```bash
# Set CONTAINER_REGISTRY in .env file
# Example: CONTAINER_REGISTRY=myregistry.azurecr.io

make publish-frontend
```

### Run Container

```bash
docker run -d \
  -e GITHUB_WEBHOOK_SECRET="..." \
  -e APPLICATIONINSIGHTS_CONNECTION_STRING="..." \
  -p 8080:8080 \
  github-telemetry-frontend
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
- `202 Accepted`: Event processed successfully
- `200 OK`: Event type not processed (ignored)
- `401 Unauthorized`: Invalid signature
- `400 Bad Request`: Invalid payload

## Telemetry Data

Telemetry data is sent to Azure Application Insights. You can query and visualize the data using Kusto Query Language (KQL) in the Application Insights portal.

```python
MetricValue(
      name="duration_seconds",
      value=duration_seconds,
      timestamp=datetime.now(UTC),
      attributes={
          "type": "workflow_run",
          "duration_seconds": str(duration_seconds),
          "queue_duration_seconds": str(queue_duration_seconds),
          "created_at": run.created_at,
          "started_at": run.run_started_at,
          "completed_at": completed_at,
          "run_id": str(run.id),
          "workflow_name": run.name,
          "run_number": str(run.run_number),
          "run_attempt": str(run.run_attempt),
          "repository_id": str(event.repository.id),
          "repository": event.repository.name,
          "repository_full_name": event.repository.full_name,
          "status": run.status,
          "conclusion": run.conclusion or "",
          "event_trigger": run.event,
          "head_branch": run.head_branch,
          "triggered_by": event.sender.login,
          "action": event.action,
          "runner_name": run.runner_name or "",
          "runner_group_name": run.runner_group_name or "",
          "labels": run.labels,
          "pool_name": self.get_mdp_name(run.labels),
          "run_url": run.html_url,
      },
  )
```


## Scaling

The webhook service can be scaled horizontally by deploying multiple instances behind a load balancer. Azure Container Apps provides automatic scaling based on HTTP traffic and custom metrics.

## License

MIT License - see [LICENSE](LICENSE) for details.