"""Test doubles shared across integration-style tests."""

import contextlib
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch


@contextlib.contextmanager
def mattermost_send_mock() -> Iterator[AsyncMock]:
    """
    Patch every import path of ``send_incoming_webhook`` used by the app.
    Open alerts use the symbol from ``api.routes``; batch flush uses the one bound in ``app``.
    """
    m = AsyncMock()
    with (
        patch("suseobs_mattermost.api.routes.send_incoming_webhook", m),
        patch("suseobs_mattermost.app.send_incoming_webhook", m),
    ):
        yield m
