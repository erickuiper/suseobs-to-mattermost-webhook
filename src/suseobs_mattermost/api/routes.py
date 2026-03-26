"""HTTP routes."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from suseobs_mattermost import __version__
from suseobs_mattermost.config import Settings
from suseobs_mattermost.models.webhook import Envelope
from suseobs_mattermost.services.formatter import render_message
from suseobs_mattermost.services.health import liveness_ok, readiness_ok
from suseobs_mattermost.services.mattermost import MattermostDeliveryError, send_incoming_webhook
from suseobs_mattermost.services.parser import envelope_to_normalized

logger = logging.getLogger(__name__)

router = APIRouter()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _check_webhook_auth(
    settings: Settings,
    authorization: str | None,
    x_webhook_token: str | None,
    x_stackstate_webhook_token: str | None,
) -> None:
    """Validate optional shared secret (see suse-obs.openapi.yaml: X-StackState-Webhook-Token)."""
    expected = settings.webhook_auth_token
    if not expected:
        return
    if x_webhook_token == expected:
        return
    if x_stackstate_webhook_token == expected:
        return
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token == expected:
            return
    raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    if not liveness_ok():
        raise HTTPException(status_code=503, detail="unhealthy")
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    if not readiness_ok():
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ready"}


@router.get("/version")
async def version() -> dict[str, str]:
    return {"version": __version__}


@router.post("/webhook/suse-obs")
async def suse_obs_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: str | None = Header(default=None),
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
    x_stackstate_webhook_token: str | None = Header(
        default=None,
        alias="X-StackState-Webhook-Token",
    ),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> JSONResponse:
    rid = x_request_id or str(uuid.uuid4())
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type != "application/json":
        logger.debug(
            "[%s] rejecting non-json content_type=%s",
            rid,
            content_type or "(missing)",
        )
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json",
        )

    _check_webhook_auth(
        settings,
        authorization,
        x_webhook_token,
        x_stackstate_webhook_token,
    )

    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.debug("[%s] invalid json: %s", rid, e)
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    try:
        envelope = Envelope.model_validate(payload)
    except ValidationError as e:
        logger.debug("[%s] validation failed: %s", rid, e)
        raise HTTPException(status_code=400, detail=e.errors()) from e

    normalized = envelope_to_normalized(envelope, settings.suse_obs_base_url)
    logger.debug(
        "[%s] normalized alert notification_id=%s summary=%s",
        rid,
        normalized.notification_id,
        normalized.summary[:200],
    )

    template = settings.resolved_message_template()
    text = render_message(template, normalized)
    logger.debug("[%s] rendered mattermost text length=%s", rid, len(text))

    try:
        await send_incoming_webhook(
            webhook_url=settings.mattermost_url,
            text=text,
            channel=settings.mattermost_channel,
            timeout_seconds=settings.mattermost_timeout_seconds,
        )
    except MattermostDeliveryError as e:
        logger.warning("[%s] mattermost delivery failed: %s", rid, e)
        raise HTTPException(status_code=502, detail="Mattermost delivery failed") from e
    except Exception as e:
        logger.exception("[%s] unexpected error delivering to Mattermost", rid)
        raise HTTPException(status_code=502, detail="Mattermost delivery failed") from e

    return JSONResponse(status_code=200, content={"status": "accepted", "request_id": rid})
