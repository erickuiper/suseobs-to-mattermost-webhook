"""Configuration tests."""

import pytest
from pydantic import ValidationError

from suseobs_mattermost.config import Settings


def test_settings_requires_mattermost_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATTERMOST_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_resolved_template_default(mattermost_env: None) -> None:
    s = Settings()
    t = s.resolved_message_template()
    assert "SUSE Observability" in t
    assert "{{" in t or "$" in t


def test_mattermost_verify_ssl_env(mattermost_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATTERMOST_VERIFY_SSL", "false")
    s = Settings()
    assert s.mattermost_verify_ssl is False
    monkeypatch.setenv("MATTERMOST_VERIFY_SSL", "true")
    assert Settings().mattermost_verify_ssl is True


def test_mattermost_ssl_ca_bundle_env(
    mattermost_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    pem = tmp_path / "corp.pem"
    pem.write_text("x")
    monkeypatch.setenv("MATTERMOST_SSL_CA_BUNDLE", str(pem))
    s = Settings()
    assert s.mattermost_ssl_ca_bundle == pem


def test_mattermost_ssl_ca_bundle_empty_none(
    mattermost_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATTERMOST_SSL_CA_BUNDLE", "")
    assert Settings().mattermost_ssl_ca_bundle is None


def test_resolved_close_message_template_default(mattermost_env: None) -> None:
    s = Settings()
    assert s.resolved_close_message_template() == ":white_check_mark: Alert closed: {{ monitor_name }}"


def test_resolved_close_message_template_override(
    mattermost_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLOSE_MESSAGE_TEMPLATE", "**{{ summary }}**")
    assert Settings().resolved_close_message_template() == "**{{ summary }}**"


def test_monitoring_batch_default_disabled(mattermost_env: None) -> None:
    """Without MONITORING_BATCH_ENABLED, every open is sent to Mattermost immediately."""
    assert Settings().monitoring_batch_enabled is False


def test_monitoring_batch_env(mattermost_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONITORING_BATCH_ENABLED", "true")
    monkeypatch.setenv("MONITORING_BATCH_WINDOW_SECONDS", "120")
    s = Settings()
    assert s.monitoring_batch_enabled is True
    assert s.monitoring_batch_window_seconds == 120.0
