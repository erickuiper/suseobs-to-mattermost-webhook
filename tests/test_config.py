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
