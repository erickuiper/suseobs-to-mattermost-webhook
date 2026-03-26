"""Structured logging setup."""

from __future__ import annotations

import logging
import re
import sys


class _RedactFilter(logging.Filter):
    """Mask incoming webhook URL path segments in log messages."""

    _hooks = re.compile(r"/hooks/[^/\s]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._hooks.sub("/hooks/***", record.msg)
        return True


def setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric)
    handler.addFilter(_RedactFilter())
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(fmt)
    root.handlers.clear()
    root.addHandler(handler)
