"""HTTP API tests."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from suseobs_mattermost.app import create_app
from suseobs_mattermost.config import Settings


def _settings() -> Settings:
    return Settings(
        mattermost_url="https://mm.example.com/hooks/abc",
        mattermost_channel="alerts",
    )


def _sample_body() -> dict:
    return {
        "notificationId": "3e9992c3-f5a9-4c85-a0fb-f8730868cb66",
        "event": {
            "type": "open",
            "state": "CRITICAL",
            "title": "Something broke",
            "triggeredTimeMs": 1701247920000,
        },
        "monitor": {
            "name": "Mon",
            "link": "https://obs.example.com/m",
            "tags": [],
        },
        "component": {
            "identifier": "urn:x",
            "link": "https://obs.example.com/c",
            "name": "Svc",
            "type": "service",
            "tags": [],
        },
        "notificationConfiguration": {"name": "nc"},
        "metadata": {},
    }


def test_healthz_readyz_version() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        r = client.get("/version")
        assert r.status_code == 200
        assert "version" in r.json()


def test_webhook_requires_json_content_type() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        r = client.post("/webhook/suse-obs", content=b"{}", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415


def test_webhook_invalid_json() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        r = client.post(
            "/webhook/suse-obs",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 400


def test_webhook_validation_error() -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        r = client.post(
            "/webhook/suse-obs",
            json={"foo": 1},
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 400


@patch("suseobs_mattermost.api.routes.send_incoming_webhook", new_callable=AsyncMock)
def test_webhook_success(mock_send: AsyncMock) -> None:
    app = create_app(_settings())
    with TestClient(app) as client:
        r = client.post(
            "/webhook/suse-obs",
            json=_sample_body(),
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 200
    assert r.json().get("status") == "accepted"
    mock_send.assert_called_once()


@patch("suseobs_mattermost.api.routes.send_incoming_webhook", new_callable=AsyncMock)
def test_webhook_auth_stackstate_header(mock_send: AsyncMock) -> None:
    """StackState spec uses X-StackState-Webhook-Token (spec/suse-obs.openapi.yaml)."""
    settings = Settings(
        mattermost_url="https://mm.example.com/hooks/abc",
        webhook_auth_token="secret",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/webhook/suse-obs",
            json=_sample_body(),
            headers={
                "Content-Type": "application/json",
                "X-StackState-Webhook-Token": "secret",
            },
        )
    assert r.status_code == 200
    mock_send.assert_called_once()


@patch("suseobs_mattermost.api.routes.send_incoming_webhook", new_callable=AsyncMock)
def test_webhook_auth_bearer(mock_send: AsyncMock) -> None:
    settings = Settings(
        mattermost_url="https://mm.example.com/hooks/abc",
        webhook_auth_token="secret",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/webhook/suse-obs",
            json=_sample_body(),
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 401
        r2 = client.post(
            "/webhook/suse-obs",
            json=_sample_body(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret"},
        )
    assert r2.status_code == 200
    mock_send.assert_called_once()


@patch("suseobs_mattermost.api.routes.send_incoming_webhook", new_callable=AsyncMock)
def test_webhook_mattermost_failure(mock_send: AsyncMock) -> None:
    from suseobs_mattermost.services.mattermost import MattermostDeliveryError

    mock_send.side_effect = MattermostDeliveryError("fail", status_code=500)
    app = create_app(_settings())
    with TestClient(app) as client:
        r = client.post(
            "/webhook/suse-obs",
            json=_sample_body(),
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 502
