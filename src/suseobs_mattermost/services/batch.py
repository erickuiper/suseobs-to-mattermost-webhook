"""Batch open alerts per monitoring source; one Mattermost message per time window."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Awaitable, Callable

from suseobs_mattermost.models.normalized import NormalizedAlert

logger = logging.getLogger(__name__)


def _md_cell(value: str) -> str:
    return value.replace("|", " ").replace("\n", " ")


def render_monitoring_batch_message(alerts: list[NormalizedAlert]) -> str:
    """Markdown table: counts per (resource name, status)."""
    if not alerts:
        return ""
    first = alerts[0]
    counts: Counter[tuple[str, str]] = Counter()
    for a in alerts:
        counts[(a.resource_name, a.status)] += 1
    lines = [
        "**SUSE Observability — batched alerts**",
        "",
        f"**Server:** {first.suse_obs_name}",
        f"**Monitor:** {first.monitor_name}",
        f"**Monitoring source:** `{first.monitoring_source_key}`",
        "",
        "**Counts by resource and status**",
        "",
        "| Resource | Status | Count |",
        "|:---|:---|---:|",
    ]
    for (res, st), n in sorted(counts.items(), key=lambda x: (x[0][0].lower(), x[0][1])):
        lines.append(f"| {_md_cell(res)} | {_md_cell(st)} | {n} |")
    lines.append("")
    lines.append(f"_Total notifications in window: {len(alerts)}_")
    return "\n".join(lines)


class MonitoringBatchCoordinator:
    """
    First open alert for a monitoring key starts a timer; further alerts with the same key
    within the window are merged. When the window elapses, one Mattermost message is sent.
    In-memory only — use a single replica or external queue if you scale horizontally.
    """

    def __init__(
        self,
        *,
        window_seconds: float,
        deliver: Callable[[str], Awaitable[None]],
    ) -> None:
        self._window = window_seconds
        self._deliver = deliver
        self._pending: dict[str, list[NormalizedAlert]] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, key: str, alert: NormalizedAlert) -> None:
        async with self._lock:
            if key not in self._pending:
                self._pending[key] = []
                self._tasks[key] = asyncio.create_task(self._flush_after(key))
            self._pending[key].append(alert)

    async def _flush_after(self, key: str) -> None:
        try:
            await asyncio.sleep(self._window)
        except asyncio.CancelledError:
            return
        async with self._lock:
            alerts = self._pending.pop(key, [])
            self._tasks.pop(key, None)
        if not alerts:
            return
        text = render_monitoring_batch_message(alerts)
        try:
            await self._deliver(text)
        except Exception:
            logger.exception("Batched Mattermost delivery failed monitoring_key=%s", key)

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
            self._pending.clear()
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
