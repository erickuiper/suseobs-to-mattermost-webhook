"""
Integration-style tests: full ASGI app, Mattermost mocked at all call sites.

Covers new open, closed, throttled follow-ups (same monitor), and independent monitors.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from suseobs_mattermost.app import create_app
from suseobs_mattermost.config import Settings
from tests.doubles import mattermost_send_mock

# Short window for speed; keep sleeps inside TestClient context.
_WINDOW = 0.08
_WAIT = 0.22


def _batch_settings(**kwargs) -> Settings:
    base = dict(
        mattermost_url="https://mm.example.com/hooks/abc",
        monitoring_batch_enabled=True,
        monitoring_batch_window_seconds=_WINDOW,
    )
    base.update(kwargs)
    return Settings(**base)


def _open_body(
    *,
    notification_id: str,
    monitor_identifier: str,
    component_name: str = "Svc",
    title: str = "Open alert",
) -> dict:
    return {
        "notificationId": notification_id,
        "event": {
            "type": "open",
            "state": "CRITICAL",
            "title": title,
            "triggeredTimeMs": 1701247920000,
        },
        "monitor": {
            "name": "HTTP Mon",
            "identifier": monitor_identifier,
            "link": "https://obs.example.com/m",
            "tags": [],
        },
        "component": {
            "identifier": f"urn:comp:{component_name}",
            "link": "https://obs.example.com/c",
            "name": component_name,
            "type": "service",
            "tags": [],
        },
        "notificationConfiguration": {"name": "nc"},
        "metadata": {},
    }


def _close_body(*, notification_id: str, monitor_identifier: str) -> dict:
    b = _open_body(
        notification_id=notification_id,
        monitor_identifier=monitor_identifier,
        title="ignored for close",
    )
    b["event"] = {"type": "close", "reason": "HealthStateResolved"}
    return b


def _post_json(client: TestClient, body: dict):
    return client.post(
        "/webhook/suse-obs",
        json=body,
        headers={"Content-Type": "application/json"},
    )


def test_integration_single_new_open_delivers_immediately() -> None:
    with mattermost_send_mock() as mock_mm:
        app = create_app(_batch_settings())
        body = _open_body(
            notification_id="11111111-1111-1111-1111-111111111111",
            monitor_identifier="urn:mon:a",
            title="First fire",
        )
        with TestClient(app) as client:
            r = _post_json(client, body)
            assert r.status_code == 200
            assert r.json().get("batched") is False
            mock_mm.assert_called_once()
            assert "First fire" in mock_mm.call_args.kwargs["text"]


def test_integration_close_delivers_immediately_not_batched() -> None:
    with mattermost_send_mock() as mock_mm:
        app = create_app(_batch_settings(close_message_template="{{ summary }}"))
        body = _close_body(
            notification_id="22222222-2222-2222-2222-222222222222",
            monitor_identifier="urn:mon:a",
        )
        with TestClient(app) as client:
            r = _post_json(client, body)
        assert r.status_code == 200
        assert "batched" not in r.json()
        mock_mm.assert_called_once()
        assert "HealthStateResolved" in mock_mm.call_args.kwargs["text"]


def test_integration_three_opens_same_monitor_one_immediate_and_one_summary() -> None:
    """Exactly the user story: 1st Mattermost now, 2nd+3rd throttled → one summary after window."""
    mid = "urn:mon:three"
    ids = (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "cccccccc-cccc-cccc-cccc-cccccccccccc",
    )
    with mattermost_send_mock() as mock_mm:
        app = create_app(_batch_settings())
        with TestClient(app) as client:
            for i, nid in enumerate(ids):
                r = _post_json(
                    client,
                    _open_body(
                        notification_id=nid,
                        monitor_identifier=mid,
                        component_name=f"Res{i}",
                        title=f"Title{i}",
                    ),
                )
                assert r.status_code == 200
                assert r.json().get("batched") is (i != 0)
            assert mock_mm.call_count == 1
            assert "Title0" in mock_mm.call_args.kwargs["text"]
            time.sleep(_WAIT)
            assert mock_mm.call_count == 2
            batch_text = mock_mm.call_args_list[1][1]["text"]
    assert "Total throttled notifications in window: 2" in batch_text
    assert "Res1" in batch_text
    assert "Res2" in batch_text


def test_integration_same_monitor_throttled_followup() -> None:
    with mattermost_send_mock() as mock_mm:
        app = create_app(_batch_settings())
        mid = "urn:mon:throttle"
        with TestClient(app) as client:
            r1 = _post_json(
                client,
                _open_body(
                    notification_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    monitor_identifier=mid,
                    component_name="Kafka",
                    title="Kafka down",
                ),
            )
            r2 = _post_json(
                client,
                _open_body(
                    notification_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    monitor_identifier=mid,
                    component_name="Redis",
                    title="Redis slow",
                ),
            )
            assert r1.json().get("batched") is False
            assert r2.json().get("batched") is True
            mock_mm.assert_called_once()
            assert "Kafka down" in mock_mm.call_args.kwargs["text"]
            time.sleep(_WAIT)
            assert mock_mm.call_count == 2
            summary = mock_mm.call_args_list[1][1]["text"]
        assert "batched alerts" in summary.lower()
        assert "Redis" in summary
        assert "Kafka" not in summary
        assert "Total throttled notifications in window: 1" in summary


def test_integration_different_monitors_both_first_opens_immediate() -> None:
    with mattermost_send_mock() as mock_mm:
        app = create_app(_batch_settings())
        with TestClient(app) as client:
            r1 = _post_json(
                client,
                _open_body(
                    notification_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
                    monitor_identifier="urn:mon:one",
                    title="One",
                ),
            )
            r2 = _post_json(
                client,
                _open_body(
                    notification_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
                    monitor_identifier="urn:mon:two",
                    title="Two",
                ),
            )
            assert r1.json().get("batched") is False
            assert r2.json().get("batched") is False
            assert mock_mm.call_count == 2
            texts = [mock_mm.call_args_list[i][1]["text"] for i in range(2)]
            assert any("One" in t for t in texts)
            assert any("Two" in t for t in texts)
            time.sleep(_WAIT)
        assert mock_mm.call_count == 2


def test_integration_mixed_open_close_then_open_after_window() -> None:
    # Open and close are immediate; after the batch window, the next open is first-of-cycle.
    with mattermost_send_mock() as mock_mm:
        app = create_app(_batch_settings())
        mid = "urn:mon:mixed"
        with TestClient(app) as client:
            _post_json(
                client,
                _open_body(
                    notification_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                    monitor_identifier=mid,
                    title="Open A",
                ),
            )
            _post_json(
                client,
                _close_body(
                    notification_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
                    monitor_identifier=mid,
                ),
            )
            assert mock_mm.call_count == 2
            time.sleep(_WAIT)
            r3 = _post_json(
                client,
                _open_body(
                    notification_id="99999999-9999-9999-9999-999999999999",
                    monitor_identifier=mid,
                    title="Open B",
                ),
            )
            assert r3.json().get("batched") is False
            assert mock_mm.call_count == 3
            assert "Open B" in mock_mm.call_args.kwargs["text"]
