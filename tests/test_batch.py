"""Monitoring batch coordinator and batch message rendering."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from suseobs_mattermost.models.normalized import NormalizedAlert
from suseobs_mattermost.services.batch import (
    MonitoringBatchCoordinator,
    render_monitoring_batch_message,
)


def _alert(resource: str, status: str, monitor_key: str = "urn:mon:a") -> NormalizedAlert:
    return NormalizedAlert(
        summary="s",
        severity="CRITICAL",
        status=status,
        error_details="e",
        resource_name=resource,
        resource_type="service",
        resource_identifier=f"urn:{resource}",
        suse_obs_name="obs",
        suse_obs_url="https://obs/",
        notification_id="nid",
        monitor_name="HTTP mon",
        monitor_link="",
        component_link="",
        is_close_event=False,
        monitoring_source_key=monitor_key,
        monitor_identifier="urn:mon:a",
    )


def test_render_batch_counts_by_resource_and_status() -> None:
    alerts = [
        _alert("Kafka", "open (CRITICAL)"),
        _alert("Kafka", "open (CRITICAL)"),
        _alert("Redis", "open (DEVIATING)"),
    ]
    text = render_monitoring_batch_message(alerts)
    assert "Kafka" in text
    assert "Redis" in text
    assert "open (CRITICAL)" in text
    assert "open (DEVIATING)" in text
    lines = [ln for ln in text.splitlines() if "Kafka" in ln and "CRITICAL" in ln]
    assert lines and "| 2 |" in lines[0]
    assert "Total notifications in window: 3" in text


@pytest.mark.asyncio
async def test_coordinator_merges_same_key_within_window() -> None:
    sent: list[str] = []

    async def capture(t: str) -> None:
        sent.append(t)

    deliver = AsyncMock(side_effect=capture)

    c = MonitoringBatchCoordinator(window_seconds=0.04, deliver=deliver)
    a1 = _alert("Kafka", "open (CRITICAL)", "urn:key1")
    a2 = _alert("Redis", "open (DEVIATING)", "urn:key1")
    await c.enqueue("urn:key1", a1)
    await c.enqueue("urn:key1", a2)
    await asyncio.sleep(0.1)
    await c.shutdown()

    deliver.assert_called_once()
    assert "Kafka" in sent[0]
    assert "Redis" in sent[0]


@pytest.mark.asyncio
async def test_coordinator_separate_keys_separate_messages() -> None:
    deliver = AsyncMock()
    c = MonitoringBatchCoordinator(window_seconds=0.04, deliver=deliver)
    await c.enqueue("urn:a", _alert("X", "open (CRITICAL)", "urn:a"))
    await c.enqueue("urn:b", _alert("Y", "open (CRITICAL)", "urn:b"))
    await asyncio.sleep(0.1)
    await c.shutdown()
    assert deliver.call_count == 2


@pytest.mark.asyncio
async def test_shutdown_cancels_pending_batch() -> None:
    deliver = AsyncMock()
    c = MonitoringBatchCoordinator(window_seconds=30.0, deliver=deliver)
    await c.enqueue("urn:x", _alert("Z", "open (CRITICAL)", "urn:x"))
    await c.shutdown()
    deliver.assert_not_called()
