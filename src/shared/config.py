"""Configuration settings for the GitHub Telemetry application.

These settings classes are resilient to placeholder environment variables that may
appear in certain development or CI environments. Unknown environment variables
are ignored and obviously non-numeric port values fall back to the default.
"""

from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    """Settings for the webhook frontend service.

    Unknown environment variables are ignored to prevent failures during import
    when placeholder values are present. A non-integer 'port' value will be
    discarded so that the default is used.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        extra="ignore",
    )

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080

    # GitHub webhook secret for signature validation
    github_webhook_secret: str = ""

    # Azure Storage Queue settings
    azure_storage_account_name: str = ""
    azure_storage_queue_name: str = "github-webhook-events"

    @model_validator(mode="before")
    def _sanitize(cls, values: dict[str, Any]) -> dict[str, Any]:
        # If port is a non-numeric placeholder string, drop it so default applies
        port_val = values.get("port")
        if isinstance(port_val, str) and not port_val.strip().isdigit():
            values.pop("port", None)
        return values


class BackendSettings(BaseSettings):
    """Settings for the webhook backend service.

    Unknown environment variables are ignored so that placeholder entries do
    not break import-time configuration.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        extra="ignore",
    )

    # Azure Storage Queue settings
    azure_storage_account_name: str = ""
    azure_storage_queue_name: str = "github-webhook-events"

    # Azure Application Insights settings
    applicationinsights_connection_string: str = ""

    # Processing settings
    poll_interval_seconds: int = 5
    max_messages_per_batch: int = 32
    visibility_timeout_seconds: int = 300
