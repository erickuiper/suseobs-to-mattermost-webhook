"""Deliver messages to Mattermost incoming webhook."""

from __future__ import annotations

import json
import logging
import ssl
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)
_insecure_tls_warned = False


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


def _mattermost_tls_verify(
    verify_ssl: bool,
    ssl_ca_bundle: Path | None,
) -> bool | str:
    """Value for httpx ``verify=`` (bool or path to PEM bundle)."""
    if not verify_ssl:
        return False
    if ssl_ca_bundle is not None:
        if not ssl_ca_bundle.is_file():
            raise MattermostDeliveryError(
                f"Mattermost TLS CA bundle path is not a file: {ssl_ca_bundle}",
            )
        return str(ssl_ca_bundle)
    return True


def _tls_failure_hint(exc: Exception) -> str | None:
    msg = str(exc).lower()
    if "certificate verify failed" in msg or "cert_verify_failed" in msg:
        return (
            "Mattermost TLS verification failed (untrusted or mismatched certificate). "
            "Set MATTERMOST_SSL_CA_BUNDLE to a PEM file containing your CA, or set "
            "MATTERMOST_VERIFY_SSL=false only for dev/test."
        )
    if isinstance(exc, ssl.SSLError):
        return (
            "Mattermost TLS error. Set MATTERMOST_SSL_CA_BUNDLE to your CA PEM, or "
            "MATTERMOST_VERIFY_SSL=false only for dev/test."
        )
    cause = getattr(exc, "__cause__", None)
    if isinstance(cause, ssl.SSLError):
        return _tls_failure_hint(cause)
    return None


def _mattermost_404_hint(body: str) -> str:
    """Mattermost often returns 404 with a JSON body when ``channel`` override is wrong."""
    try:
        j = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return ""
    mid = str(j.get("id") or "")
    if "incoming_webhook" not in mid:
        return ""
    return (
        " Often caused by MATTERMOST_CHANNEL: use the channel handle (URL slug: lowercase, "
        "hyphens), not the display name, or unset MATTERMOST_CHANNEL to use the webhook default."
    )


async def send_incoming_webhook(
    *,
    webhook_url: str,
    text: str,
    channel: str | None,
    timeout_seconds: float,
    verify_ssl: bool = True,
    ssl_ca_bundle: Path | None = None,
) -> None:
    payload = build_payload(text, channel)
    timeout = httpx.Timeout(timeout_seconds)
    tls_verify = _mattermost_tls_verify(verify_ssl, ssl_ca_bundle)
    global _insecure_tls_warned
    if not verify_ssl and not _insecure_tls_warned:
        _insecure_tls_warned = True
        logger.warning(
            "Mattermost TLS verification disabled (MATTERMOST_VERIFY_SSL=false); "
            "use only for dev/test or fix the server certificate",
        )
    async with httpx.AsyncClient(timeout=timeout, verify=tls_verify) as client:
        logger.debug(
            "Posting to Mattermost webhook host=%s channel=%s text_len=%s tls_verify=%s",
            _safe_host(webhook_url),
            channel or "(default)",
            len(text),
            tls_verify,
        )
        try:
            resp = await client.post(webhook_url, json=payload)
        except httpx.TimeoutException as e:
            raise MattermostDeliveryError("Mattermost request timed out") from e
        except httpx.RequestError as e:
            hint = _tls_failure_hint(e)
            if hint:
                raise MattermostDeliveryError(f"{hint} ({e})") from e
            raise MattermostDeliveryError(f"Mattermost request failed: {e}") from e
        if resp.status_code >= 400:
            snippet = (resp.text or "")[:500]
            hint = _mattermost_404_hint(resp.text or "") if resp.status_code == 404 else ""
            if hint:
                logger.warning(
                    "Mattermost error status=%s body_snippet=%s%s",
                    resp.status_code,
                    snippet,
                    hint,
                )
            else:
                logger.warning(
                    "Mattermost error status=%s body_snippet=%s",
                    resp.status_code,
                    snippet,
                )
            msg = f"Mattermost returned {resp.status_code}"
            if hint:
                msg += "." + hint
            raise MattermostDeliveryError(msg, status_code=resp.status_code)


def _safe_host(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"
