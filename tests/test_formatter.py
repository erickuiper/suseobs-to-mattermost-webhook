"""Template rendering tests."""

from suseobs_mattermost.models.normalized import NormalizedAlert
from suseobs_mattermost.services.formatter import render_message


def _alert() -> NormalizedAlert:
    return NormalizedAlert(
        summary="s",
        severity="sev",
        status="st",
        error_details="err",
        resource_name="rn",
        resource_type="rt",
        resource_identifier="ri",
        suse_obs_name="obs",
        suse_obs_url="https://obs/",
        notification_id="nid",
        monitor_name="mn",
        monitor_link="ml",
        component_link="cl",
    )


def test_mustache_placeholders() -> None:
    t = "**x** {{ summary }} — {{ resource_name }}"
    out = render_message(t, _alert())
    assert "s" in out
    assert "rn" in out


def test_dollar_template() -> None:
    t = "Hello $summary / ${resource_name}"
    out = render_message(t, _alert())
    assert "s" in out
    assert "rn" in out
