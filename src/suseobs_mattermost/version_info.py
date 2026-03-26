"""Runtime version from build-time env (CI/Docker) or package default."""

from __future__ import annotations

import os

from suseobs_mattermost import __version__


def get_version() -> str:
    """Semver or `0.1.0+<short-sha>` on main builds; set via Docker `APP_VERSION`."""
    return os.environ.get("APP_VERSION") or __version__


def get_git_sha() -> str:
    """Git commit SHA at image build; set via Docker `GIT_SHA`."""
    return os.environ.get("GIT_SHA") or "unknown"
