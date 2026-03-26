"""Runtime version helpers."""

import pytest

from suseobs_mattermost import __version__
from suseobs_mattermost.version_info import get_git_sha, get_version


def test_get_version_default() -> None:
    assert get_version() == __version__


def test_get_git_sha_default() -> None:
    assert get_git_sha() == "unknown"


def test_get_version_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    assert get_version() == "9.9.9"


def test_get_git_sha_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA", "abc1234")
    assert get_git_sha() == "abc1234"
