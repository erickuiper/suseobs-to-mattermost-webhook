"""Mattermost client tests."""

from unittest.mock import AsyncMock, MagicMock, patch

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
