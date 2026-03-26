"""Uvicorn entrypoint."""

import uvicorn

from suseobs_mattermost.app import create_app
from suseobs_mattermost.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
