"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from suseobs_mattermost import __version__
from suseobs_mattermost.api.routes import router
from suseobs_mattermost.config import Settings, load_settings
from suseobs_mattermost.logging_config import setup_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        _app.state.settings = settings
        yield

    app = FastAPI(
        title="SUSE Observability → Mattermost",
        version=__version__,
        lifespan=lifespan,
    )
    app.include_router(router)
    return app
