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

    message_template: str | None = Field(default=None, validation_alias="MESSAGE_TEMPLATE")
    message_template_path: Path | None = Field(
        default=None,
        validation_alias="MESSAGE_TEMPLATE_PATH",
    )

    suse_obs_base_url: str | None = Field(default=None, validation_alias="SUSE_OBS_BASE_URL")

    webhook_auth_token: str | None = Field(default=None, validation_alias="WEBHOOK_AUTH_TOKEN")

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

    def resolved_message_template(self) -> str:
        if self.message_template_path is not None:
            path = self.message_template_path
            return path.read_text(encoding="utf-8")
        if self.message_template:
            return self.message_template
        return DEFAULT_MESSAGE_TEMPLATE


def load_settings() -> Settings:
    return Settings()
