"""Pydantic models aligned with spec/suse-obs.webhook-api.yaml."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpenEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["open"]
    state: Literal["DEVIATING", "CRITICAL"]
    title: str
    triggeredTimeMs: int
    reason: str | None = None


class CloseEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["close"]
    reason: Literal[
        "ConfigRemoved",
        "ConfigChanged",
        "ComponentRemoved",
        "ComponentChanged",
        "HealthStateResolved",
        "ChannelRemoved",
    ]


class Monitor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    identifier: str | None = None
    link: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return [f"{k}={val}" for k, val in v.items()]
        return v


class Component(BaseModel):
    model_config = ConfigDict(extra="ignore")

    identifier: str
    link: str
    name: str
    type: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return [f"{k}={val}" for k, val in v.items()]
        return v


class NotificationConfiguration(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    identifier: str | None = None
    link: str | None = None


class Envelope(BaseModel):
    """StackState / SUSE Observability webhook envelope (spec)."""

    model_config = ConfigDict(extra="ignore")

    notificationId: UUID
    event: OpenEvent | CloseEvent = Field(discriminator="type")
    monitor: Monitor
    component: Component
    notificationConfiguration: NotificationConfiguration
    metadata: dict[str, str]
