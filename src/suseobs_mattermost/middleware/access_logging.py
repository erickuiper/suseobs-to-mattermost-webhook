"""Access-style request logging without flooding INFO on Kubernetes probes."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_LOG = logging.getLogger("suseobs_mattermost.access")

# Log these at DEBUG only so default LOG_LEVEL=INFO stays quiet under probe traffic.
_PROBE_PATHS = frozenset({"/healthz", "/readyz"})


class ProbeQuietAccessLogMiddleware(BaseHTTPMiddleware):
    """Mimic uvicorn access lines: probes → DEBUG, other routes → INFO."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        client = request.client
        host = client.host if client else "-"
        port = client.port if client else 0
        msg = f'{host}:{port} - "{request.method} {path} HTTP/1.1" {response.status_code}'
        if path in _PROBE_PATHS:
            _LOG.debug(msg)
        else:
            _LOG.info(msg)
        return response
