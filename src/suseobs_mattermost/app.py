"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from suseobs_mattermost.api.routes import router
from suseobs_mattermost.config import Settings, load_settings
from suseobs_mattermost.logging_config import setup_logging
from suseobs_mattermost.middleware.access_logging import ProbeQuietAccessLogMiddleware
from suseobs_mattermost.services.batch import MonitoringBatchCoordinator
from suseobs_mattermost.services.mattermost import send_incoming_webhook
from suseobs_mattermost.version_info import get_version

_log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings

        async def deliver_batched(text: str) -> None:
            await send_incoming_webhook(
                webhook_url=settings.mattermost_url,
                text=text,
                channel=settings.mattermost_channel,
                timeout_seconds=settings.mattermost_timeout_seconds,
                verify_ssl=settings.mattermost_verify_ssl,
                ssl_ca_bundle=settings.mattermost_ssl_ca_bundle,
            )

        if settings.monitoring_batch_enabled:
            app.state.monitoring_batch = MonitoringBatchCoordinator(
                window_seconds=settings.monitoring_batch_window_seconds,
                deliver_batch=deliver_batched,
            )
            _log.info(
                "Open-alert batching enabled: first open per monitor is sent immediately; "
                "further opens within %.2fs are summarized in one Mattermost message. "
                "Use a single replica (or disable batching) if you scale horizontally.",
                settings.monitoring_batch_window_seconds,
            )
        else:
            app.state.monitoring_batch = None
            _log.info(
                "Open-alert batching is off (MONITORING_BATCH_ENABLED=false or unset): "
                "every open webhook is sent to Mattermost immediately. "
                "Set MONITORING_BATCH_ENABLED=true to throttle follow-ups per monitor.",
            )

        yield

        batch = app.state.monitoring_batch
        if batch is not None:
            await batch.shutdown()

    app = FastAPI(
        title="SUSE Observability → Mattermost",
        version=get_version(),
        lifespan=lifespan,
    )
    app.add_middleware(ProbeQuietAccessLogMiddleware)
    app.include_router(router)
    return app
