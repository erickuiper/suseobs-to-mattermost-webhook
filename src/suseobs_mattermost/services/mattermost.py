"""Deliver messages to Mattermost incoming webhook."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MattermostDeliveryError(Exception):
    """Raised when Mattermost returns an error or times out."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def build_payload(text: str, channel: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"text": text}
    if channel:
        body["channel"] = channel
    return body


async def send_incoming_webhook(
    *,
    webhook_url: str,
    text: str,
    channel: str | None,
    timeout_seconds: float,
) -> None:
    payload = build_payload(text, channel)
    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        logger.debug(
            "Posting to Mattermost webhook host=%s channel=%s text_len=%s",
            _safe_host(webhook_url),
            channel or "(default)",
            len(text),
        )
        try:
            resp = await client.post(webhook_url, json=payload)
        except httpx.TimeoutException as e:
            raise MattermostDeliveryError("Mattermost request timed out") from e
        except httpx.RequestError as e:
            raise MattermostDeliveryError(f"Mattermost request failed: {e}") from e
        if resp.status_code >= 400:
            snippet = (resp.text or "")[:500]
            logger.warning(
                "Mattermost error status=%s body_snippet=%s",
                resp.status_code,
                snippet,
            )
            raise MattermostDeliveryError(
                f"Mattermost returned {resp.status_code}",
                status_code=resp.status_code,
            )


def _safe_host(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"
