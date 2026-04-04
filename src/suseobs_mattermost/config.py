"""Environment-driven configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MESSAGE_TEMPLATE = """**SUSE Observability Alert**

**Error**
- Summary: {{ summary }}
- Severity: {{ severity }}
- Status: {{ status }}
- Details: {{ error_details }}

**Affected resource**
- Name: {{ resource_name }}
- Type: {{ resource_type }}
- Identifier: {{ resource_identifier }}

**Source**
- Server: {{ suse_obs_name }}
- URL: {{ suse_obs_url }}
- Monitor: {{ monitor_name }}
"""

DEFAULT_CLOSE_MESSAGE_TEMPLATE = "{{ summary }}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8080, validation_alias="APP_PORT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    mattermost_url: str = Field(validation_alias="MATTERMOST_URL")
    mattermost_channel: str | None = Field(default=None, validation_alias="MATTERMOST_CHANNEL")
    mattermost_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="MATTERMOST_TIMEOUT_SECONDS",
    )
    mattermost_verify_ssl: bool = Field(default=True, validation_alias="MATTERMOST_VERIFY_SSL")
    mattermost_ssl_ca_bundle: Path | None = Field(
        default=None,
        validation_alias="MATTERMOST_SSL_CA_BUNDLE",
        description="Path to PEM file (custom CA) for Mattermost HTTPS verification",
    )

    message_template: str | None = Field(default=None, validation_alias="MESSAGE_TEMPLATE")
    message_template_path: Path | None = Field(
        default=None,
        validation_alias="MESSAGE_TEMPLATE_PATH",
    )

    suse_obs_base_url: str | None = Field(default=None, validation_alias="SUSE_OBS_BASE_URL")

    webhook_auth_token: str | None = Field(default=None, validation_alias="WEBHOOK_AUTH_TOKEN")

    close_message_template: str | None = Field(
        default=None,
        validation_alias="CLOSE_MESSAGE_TEMPLATE",
    )
    monitoring_batch_enabled: bool = Field(
        default=False,
        validation_alias="MONITORING_BATCH_ENABLED",
        description=(
            "When false (default), each open alert is sent to Mattermost immediately. "
            "When true, the first open per monitor posts immediately and further opens "
            "within MONITORING_BATCH_WINDOW_SECONDS are combined into one message."
        ),
    )
    monitoring_batch_window_seconds: float = Field(
        default=60.0,
        ge=0.01,
        validation_alias="MONITORING_BATCH_WINDOW_SECONDS",
    )

    @field_validator("log_level")
    @classmethod
    def upper_log_level(cls, v: str) -> str:
        return v.upper()

    @field_validator("mattermost_verify_ssl", mode="before")
    @classmethod
    def parse_verify_ssl(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("0", "false", "no", "off"):
                return False
            if s in ("1", "true", "yes", "on"):
                return True
        return bool(v)

    @field_validator("monitoring_batch_enabled", mode="before")
    @classmethod
    def parse_monitoring_batch_enabled(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("0", "false", "no", "off"):
                return False
            if s in ("1", "true", "yes", "on"):
                return True
        return bool(v)

    @field_validator("mattermost_ssl_ca_bundle", mode="before")
    @classmethod
    def empty_ca_bundle_none(cls, v: Any) -> Path | None:
        if v is None or v == "":
            return None
        return v

    def resolved_message_template(self) -> str:
        if self.message_template_path is not None:
            path = self.message_template_path
            return path.read_text(encoding="utf-8")
        if self.message_template:
            return self.message_template
        return DEFAULT_MESSAGE_TEMPLATE

    def resolved_close_message_template(self) -> str:
        if self.close_message_template:
            return self.close_message_template
        return DEFAULT_CLOSE_MESSAGE_TEMPLATE


def load_settings() -> Settings:
    return Settings()
