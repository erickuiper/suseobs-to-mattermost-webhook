"""Mattermost client tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from suseobs_mattermost.services.mattermost import (
    MattermostDeliveryError,
    build_payload,
    send_incoming_webhook,
)


def test_build_payload() -> None:
    p = build_payload("hello", "town-square")
    assert p["text"] == "hello"
    assert p["channel"] == "town-square"


def test_build_payload_no_channel() -> None:
    p = build_payload("hello", None)
    assert "channel" not in p


def _mock_client_ok() -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "ok"
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


@pytest.mark.asyncio
async def test_send_success() -> None:
    mock_client = _mock_client_ok()
    target = "suseobs_mattermost.services.mattermost.httpx.AsyncClient"
    with patch(target, return_value=mock_client):
        await send_incoming_webhook(
            webhook_url="https://mm.example.com/hooks/abc",
            text="t",
            channel=None,
            timeout_seconds=5.0,
            verify_ssl=True,
        )
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_uses_ca_bundle_path(tmp_path: Path) -> None:
    pem = tmp_path / "ca.pem"
    pem.write_text("-----BEGIN CERTIFICATE-----\nZm9v\n-----END CERTIFICATE-----\n")
    mock_client = _mock_client_ok()
    target = "suseobs_mattermost.services.mattermost.httpx.AsyncClient"
    with patch(target, return_value=mock_client) as ctor:
        await send_incoming_webhook(
            webhook_url="https://mm.example.com/hooks/abc",
            text="t",
            channel=None,
            timeout_seconds=5.0,
            verify_ssl=True,
            ssl_ca_bundle=pem,
        )
    ctor.assert_called_once()
    assert ctor.call_args.kwargs["verify"] == str(pem)


@pytest.mark.asyncio
async def test_send_missing_ca_bundle_file() -> None:
    missing = Path("/nonexistent/ca-bundle.pem")
    with pytest.raises(MattermostDeliveryError, match="CA bundle path"):
        await send_incoming_webhook(
            webhook_url="https://mm.example.com/hooks/abc",
            text="t",
            channel=None,
            timeout_seconds=5.0,
            verify_ssl=True,
            ssl_ca_bundle=missing,
        )


@pytest.mark.asyncio
async def test_send_tls_cert_error_includes_hint() -> None:
    mock_client = MagicMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.ConnectError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
            request=MagicMock(),
        ),
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    target = "suseobs_mattermost.services.mattermost.httpx.AsyncClient"
    with patch(target, return_value=mock_client):
        with pytest.raises(MattermostDeliveryError) as ei:
            await send_incoming_webhook(
                webhook_url="https://mm.example.com/hooks/abc",
                text="t",
                channel=None,
                timeout_seconds=5.0,
                verify_ssl=True,
            )
    assert "MATTERMOST_SSL_CA_BUNDLE" in str(ei.value)


@pytest.mark.asyncio
async def test_send_404_includes_channel_hint() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = (
        '{"id":"web.incoming_webhook.general.app_error","message":"Failed to handle payload"}'
    )
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    target = "suseobs_mattermost.services.mattermost.httpx.AsyncClient"
    with patch(target, return_value=mock_client):
        with pytest.raises(MattermostDeliveryError) as ei:
            await send_incoming_webhook(
                webhook_url="https://mm.example.com/hooks/abc",
                text="t",
                channel=None,
                timeout_seconds=5.0,
                verify_ssl=True,
            )
    assert "MATTERMOST_CHANNEL" in str(ei.value)


@pytest.mark.asyncio
async def test_send_http_error() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = "bad"
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    target = "suseobs_mattermost.services.mattermost.httpx.AsyncClient"
    with patch(target, return_value=mock_client):
        with pytest.raises(MattermostDeliveryError):
            await send_incoming_webhook(
                webhook_url="https://mm.example.com/hooks/abc",
                text="t",
                channel=None,
                timeout_seconds=5.0,
                verify_ssl=True,
            )
