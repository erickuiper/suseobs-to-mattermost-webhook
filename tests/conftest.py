"""Shared fixtures."""

import pytest

from suseobs_mattermost.config import Settings


@pytest.fixture
def mattermost_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATTERMOST_URL", "https://mattermost.example.com/hooks/testhooktoken")


@pytest.fixture
def test_settings(mattermost_env: None) -> Settings:
    return Settings()
