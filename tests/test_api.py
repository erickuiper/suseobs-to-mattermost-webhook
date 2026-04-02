"""HTTP API tests."""

import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from suseobs_mattermost.app import create_app
from suseobs_mattermost.config import Settings


def _settings(**kwargs) -> Settings:
    base = dict(
        mattermost_url="https://mm.example.com/hooks/abc",
        mattermost_channel="alerts",
        monitoring_batch_enabled=False,
    )
    base.update(kwargs)
    return Settings(**base)


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
        body = r.json()
        assert "version" in body
        assert "git_sha" in body


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
def test_webhook_close_uses_close_template(mock_send: AsyncMock) -> None:
    body = _sample_body()
    body["event"] = {"type": "close", "reason": "HealthStateResolved"}
    app = create_app(_settings(close_message_template="CLOSED: {{ summary }}"))
    with TestClient(app) as client:
        r = client.post(
            "/webhook/suse-obs",
            json=body,
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 200
    mock_send.assert_called_once()
    text = mock_send.call_args.kwargs["text"]
    assert text.startswith("CLOSED: ")
    assert "HealthStateResolved" in text


@patch("suseobs_mattermost.app.send_incoming_webhook", new_callable=AsyncMock)
def test_webhook_batch_deferred_delivery(mock_send: AsyncMock) -> None:
    body = _sample_body()
    body["monitor"]["identifier"] = "urn:batch:test"
    app = create_app(
        _settings(
            monitoring_batch_enabled=True,
            monitoring_batch_window_seconds=0.06,
        ),
    )
    with TestClient(app) as client:
        r1 = client.post(
            "/webhook/suse-obs",
            json=body,
            headers={"Content-Type": "application/json"},
        )
        body2 = {**body, "notificationId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
        body2["component"] = {**body["component"], "name": "OtherSvc"}
        r2 = client.post(
            "/webhook/suse-obs",
            json=body2,
            headers={"Content-Type": "application/json"},
        )
        assert r1.status_code == 200
        assert r1.json().get("batched") is True
        assert r2.status_code == 200
        mock_send.assert_not_called()
        # Stay inside TestClient so lifespan does not cancel batch timers.
        time.sleep(0.15)
        mock_send.assert_called_once()
        batched = mock_send.call_args.kwargs["text"]
    assert "Svc" in batched or "OtherSvc" in batched
    assert "batched alerts" in batched.lower()


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
