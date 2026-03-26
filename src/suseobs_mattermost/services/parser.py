"""Map StackState envelope (spec) to NormalizedAlert."""

from __future__ import annotations

from urllib.parse import urlparse

from suseobs_mattermost.models.normalized import NormalizedAlert
from suseobs_mattermost.models.webhook import Envelope, OpenEvent


def _pick_suse_obs_url(envelope: Envelope, base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    for candidate in (
        envelope.monitor.link,
        envelope.component.link,
        envelope.notificationConfiguration.link,
    ):
        if candidate:
            return candidate
    return ""


def _derive_server_name(envelope: Envelope, suse_obs_url: str) -> str:
    name = envelope.notificationConfiguration.name.strip()
    if name:
        return name
    meta = envelope.metadata.get("serverName") or envelope.metadata.get("stackstateUrl")
    if meta:
        return meta
    if suse_obs_url:
        parsed = urlparse(suse_obs_url)
        host = parsed.netloc or parsed.path
        return host or "SUSE Observability"
    return "SUSE Observability"


def envelope_to_normalized(envelope: Envelope, suse_obs_base_url: str | None) -> NormalizedAlert:
    """Build normalized alert from validated webhook envelope."""
    comp = envelope.component
    mon = envelope.monitor
    ev = envelope.event
    suse_obs_url = _pick_suse_obs_url(envelope, suse_obs_base_url)
    suse_obs_name = _derive_server_name(envelope, suse_obs_url)

    monitor_link = (mon.link or "").strip()
    component_link = (comp.link or "").strip()

    if isinstance(ev, OpenEvent):
        summary = ev.title
        severity = ev.state
        status = f"open ({ev.state})"
        error_parts = [ev.title]
        if ev.reason:
            error_parts.append(ev.reason)
        error_details = "\n".join(error_parts)
    else:
        # CloseEvent — spec oneOf close
        summary = f"Alert closed: {ev.reason}"
        severity = "resolved"
        status = "closed"
        error_details = ev.reason

    return NormalizedAlert(
        summary=summary,
        severity=severity,
        status=status,
        error_details=error_details,
        resource_name=comp.name,
        resource_type=comp.type,
        resource_identifier=comp.identifier,
        suse_obs_name=suse_obs_name,
        suse_obs_url=suse_obs_url,
        notification_id=str(envelope.notificationId),
        monitor_name=mon.name,
        monitor_link=monitor_link,
        component_link=component_link,
    )
