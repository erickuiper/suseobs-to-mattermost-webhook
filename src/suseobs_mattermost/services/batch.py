"""Batch follow-up open alerts per monitoring source after an immediate first delivery."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from suseobs_mattermost.models.normalized import NormalizedAlert

logger = logging.getLogger(__name__)


def _md_cell(value: str) -> str:
    return value.replace("|", " ").replace("\n", " ")


def render_monitoring_batch_message(alerts: list[NormalizedAlert]) -> str:
    """Markdown table: counts per (resource name, status) for throttled follow-up opens."""
    if not alerts:
        return ""
    first = alerts[0]
    counts: Counter[tuple[str, str]] = Counter()
    for a in alerts:
        counts[(a.resource_name, a.status)] += 1
    lines = [
        "**SUSE Observability — batched alerts**",
        "",
        "_Additional notifications for the same monitor within the batch window "
        "(after the first alert was delivered immediately)._",
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
    lines.append(f"_Total throttled notifications in window: {len(alerts)}_")
    return "\n".join(lines)


@dataclass
class _Session:
    buffer: list[NormalizedAlert]
    task: asyncio.Task[None]


class MonitoringBatchCoordinator:
    """
    Per ``monitoring_source_key``:

    - The **first** open alert in a quiet period is delivered immediately (via
      ``deliver_individual``) and starts the batch window.
    - **Further** opens for the same key before the window ends are held; when the
      window expires, **one** combined Mattermost message is sent for those follow-ups.
    - A **different** key is independent: its first open is also delivered immediately,
      even if another key's window is still running.

    In-memory only — use a single replica or disable batching when scaling out.
    """

    def __init__(
        self,
        *,
        window_seconds: float,
        deliver_batch: Callable[[str], Awaitable[None]],
    ) -> None:
        self._window = window_seconds
        self._deliver_batch = deliver_batch
        self._sessions: dict[str, _Session] = {}
        self._lock = asyncio.Lock()

    async def process_open(
        self,
        key: str,
        alert: NormalizedAlert,
        *,
        deliver_individual: Callable[[NormalizedAlert], Awaitable[None]],
    ) -> bool:
        """
        Handle one open alert. Returns ``True`` if this request performed immediate
        individual delivery; ``False`` if it was queued for the batch summary.
        """
        immediate = False
        async with self._lock:
            if key not in self._sessions:
                self._sessions[key] = _Session(
                    buffer=[],
                    task=asyncio.create_task(self._flush_after(key)),
                )
                immediate = True
            else:
                self._sessions[key].buffer.append(alert)

        if immediate:
            await deliver_individual(alert)
        return immediate

    async def _flush_after(self, key: str) -> None:
        try:
            await asyncio.sleep(self._window)
        except asyncio.CancelledError:
            return
        async with self._lock:
            session = self._sessions.pop(key, None)
        if session is None:
            return
        buffer = session.buffer
        if not buffer:
            return
        text = render_monitoring_batch_message(buffer)
        try:
            await self._deliver_batch(text)
        except Exception:
            logger.exception("Batched Mattermost delivery failed monitoring_key=%s", key)

    async def shutdown(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for s in sessions:
            s.task.cancel()
        for s in sessions:
            try:
                await s.task
            except asyncio.CancelledError:
                pass
