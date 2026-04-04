"""
Monitoring batch coordinator and batch message rendering.

Throttling only applies when ``MONITORING_BATCH_ENABLED=true`` (see README). Unit tests
here assume the coordinator is used; API tests cover the default (batching off → every
open posts to Mattermost immediately).
"""

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
    assert "Total throttled notifications in window: 3" in text


@pytest.mark.asyncio
async def test_first_open_immediate_followups_batched() -> None:
    indiv = AsyncMock()
    batch_deliver = AsyncMock()
    c = MonitoringBatchCoordinator(window_seconds=0.05, deliver_batch=batch_deliver)
    a1 = _alert("Kafka", "open (CRITICAL)", "urn:key1")
    a2 = _alert("Redis", "open (DEVIATING)", "urn:key1")

    assert await c.process_open("urn:key1", a1, deliver_individual=indiv) is True
    indiv.assert_called_once_with(a1)

    assert await c.process_open("urn:key1", a2, deliver_individual=indiv) is False
    indiv.assert_called_once()

    await asyncio.sleep(0.12)
    batch_deliver.assert_called_once()
    combined = batch_deliver.call_args[0][0]
    assert "Redis" in combined
    assert "Total throttled notifications in window: 1" in combined
    await c.shutdown()


@pytest.mark.asyncio
async def test_different_keys_each_first_is_immediate_no_batch_message() -> None:
    """Separate monitoring contexts: each first open is delivered now; no follow-ups → no batch."""
    indiv = AsyncMock()
    batch_deliver = AsyncMock()
    c = MonitoringBatchCoordinator(window_seconds=0.05, deliver_batch=batch_deliver)
    await c.process_open("urn:a", _alert("X", "open (CRITICAL)", "urn:a"), deliver_individual=indiv)
    await c.process_open("urn:b", _alert("Y", "open (CRITICAL)", "urn:b"), deliver_individual=indiv)
    await asyncio.sleep(0.12)
    assert indiv.call_count == 2
    batch_deliver.assert_not_called()
    await c.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_pending_timer_only_first_sent() -> None:
    indiv = AsyncMock()
    batch_deliver = AsyncMock()
    c = MonitoringBatchCoordinator(window_seconds=30.0, deliver_batch=batch_deliver)
    await c.process_open("urn:x", _alert("Z", "open (CRITICAL)", "urn:x"), deliver_individual=indiv)
    indiv.assert_called_once()
    await c.shutdown()
    batch_deliver.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_drops_queued_followups() -> None:
    indiv = AsyncMock()
    batch_deliver = AsyncMock()
    c = MonitoringBatchCoordinator(window_seconds=30.0, deliver_batch=batch_deliver)
    a1 = _alert("A", "open (CRITICAL)", "k")
    a2 = _alert("B", "open (CRITICAL)", "k")
    await c.process_open("k", a1, deliver_individual=indiv)
    await c.process_open("k", a2, deliver_individual=indiv)
    await c.shutdown()
    indiv.assert_called_once()
    batch_deliver.assert_not_called()
