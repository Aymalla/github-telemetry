"""Configuration settings for the GitHub Telemetry application.

These settings classes are resilient to placeholder environment variables that may
appear in certain development or CI environments. Unknown environment variables
are ignored and obviously non-numeric port values fall back to the default.
"""

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

    # Azure Application Insights settings
    applicationinsights_connection_string: str = ""

    @model_validator(mode="before")
    @classmethod
    def _sanitize(cls, values: dict[str, object]) -> dict[str, object]:
        # If port is a non-numeric placeholder string, drop it so default applies
        if isinstance(values, dict):
            port_val = values.get("port")
            if isinstance(port_val, str):
                try:
                    int(port_val.strip())
                except (ValueError, TypeError):
                    values.pop("port", None)
        return values
