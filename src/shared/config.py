"""Configuration settings for the GitHub Telemetry application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    """Settings for the webhook frontend service."""

    model_config = SettingsConfigDict(env_prefix="FRONTEND_", env_file=".env")

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080

    # GitHub webhook secret for signature validation
    github_webhook_secret: str = ""

    # Azure Storage Queue settings
    azure_storage_connection_string: str = ""
    azure_storage_queue_name: str = "github-webhook-events"


class BackendSettings(BaseSettings):
    """Settings for the webhook backend service."""

    model_config = SettingsConfigDict(env_prefix="BACKEND_", env_file=".env")

    # Azure Storage Queue settings
    azure_storage_connection_string: str = ""
    azure_storage_queue_name: str = "github-webhook-events"

    # Azure Application Insights settings
    applicationinsights_connection_string: str = ""

    # Processing settings
    poll_interval_seconds: int = 5
    max_messages_per_batch: int = 32
    visibility_timeout_seconds: int = 300
