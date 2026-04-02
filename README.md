# SUSE Observability → Mattermost webhook bridge

Small **Python** service that receives **SUSE Observability** (StackState-compatible) webhooks, maps them to a normalized alert model, renders a configurable **Mattermost** markdown message, and posts it to an **incoming webhook** URL.

Inbound payloads follow [`spec/suse-obs.webhook-api.yaml`](spec/suse-obs.webhook-api.yaml). StackState’s root OpenAPI in [`spec/suse-obs.openapi.yaml`](spec/suse-obs.openapi.yaml) references that file and documents optional security via **`X-StackState-Webhook-Token`** (map the same value to `WEBHOOK_AUTH_TOKEN` here). Mattermost behavior follows [`spec/mattermost.md`](spec/mattermost.md) (incoming webhooks: JSON with a `text` field, optional `channel` override).

## Architecture

- **FastAPI** HTTP server
- **Pydantic** models for the StackState `Envelope` and discriminated `event` (`open` / `close`)
- **Normalized alert** (`NormalizedAlert`) used only for templating and delivery; **close** events use `CLOSE_MESSAGE_TEMPLATE`; optional **open**-event batching per monitoring source
- **string.Template** + `{{ mustache }}`-style placeholders for safe, deterministic rendering (no arbitrary code execution)
- **httpx** async client to POST to Mattermost
- **Kubernetes**: `GET /healthz` (liveness), `GET /readyz` (readiness), `GET /version`

## Configuration

Environment variables (see [`examples/.env.example`](examples/.env.example)):

| Variable | Required | Description |
|----------|----------|-------------|
| `MATTERMOST_URL` | yes | Full incoming webhook URL (`https://…/hooks/…`) — **secret** |
| `MATTERMOST_CHANNEL` | no | Optional channel override: use the **channel handle** (URL slug: lowercase, hyphens, e.g. `alerts` not `Alerts`). Wrong values cause Mattermost **404**. Omit to use the webhook’s configured default channel. |
| `MATTERMOST_TIMEOUT_SECONDS` | no | Outbound HTTP timeout (default `10`) |
| `MATTERMOST_VERIFY_SSL` | no | Verify TLS for Mattermost HTTPS (default `true`; set `false` only for dev/test with invalid certs) |
| `MATTERMOST_SSL_CA_BUNDLE` | no | Path to a PEM file with extra CA cert(s) for Mattermost (internal CA / self-signed); preferred over disabling verification |
| `LOG_LEVEL` | no | `INFO`, `DEBUG`, etc. |
| `APP_HOST` / `APP_PORT` | no | Bind address (default `0.0.0.0:8080`) |
| `MESSAGE_TEMPLATE` | no | Inline template string |
| `MESSAGE_TEMPLATE_PATH` | no | Path to template file (wins over `MESSAGE_TEMPLATE` if set) |
| `SUSE_OBS_BASE_URL` | no | If set, used as the primary “server URL” in messages instead of links from the payload |
| `WEBHOOK_AUTH_TOKEN` | no | If set, callers must send `X-StackState-Webhook-Token: …` (per StackState spec), or `Authorization: Bearer …`, or `X-Webhook-Token: …` |
| `CLOSE_MESSAGE_TEMPLATE` | no | Mattermost text for **close** events only (default `{{ summary }}` — summary-only line) |
| `MONITORING_BATCH_ENABLED` | no | If `true`, the **first** **open** per monitor is sent immediately; further opens for the same monitor within the window are combined into **one** summary when the window ends. Another monitor’s first open is still immediate (default `false`) |
| `MONITORING_BATCH_WINDOW_SECONDS` | no | Batch window length in seconds (default `60`; minimum `0.01`). **In-memory only** — use one replica when batching is enabled |

Required settings are validated at startup; the process fails fast if `MATTERMOST_URL` is missing.

## Message templating

Default template is Markdown suitable for Mattermost (`**bold**`, lists, etc.). Placeholders:

- `{{ summary }}`, `{{ severity }}`, `{{ status }}`, `{{ error_details }}`, `{{ monitor_identifier }}`, `{{ monitoring_source_key }}`
- `{{ resource_name }}`, `{{ resource_type }}`, `{{ resource_identifier }}`
- `{{ suse_obs_name }}`, `{{ suse_obs_url }}`
- `{{ notification_id }}`, `{{ monitor_name }}`, `{{ monitor_link }}`, `{{ component_link }}`

After `{{ … }}` substitution, Python’s `string.Template` runs so you can also use `$summary` or `${resource_name}`.

## Assumptions (from the spec)

- Inbound body matches `Envelope` in `spec/suse-obs.webhook-api.yaml` (`notificationId`, `event`, `monitor`, `component`, `notificationConfiguration`, `metadata`).
- `event` is either **open** (with `state`, `title`, `triggeredTimeMs`) or **close** (with `reason` enum).
- Monitor `tags` in the spec are an array of strings; some deployments send objects — those are coerced to string pairs for internal use.
- **Server display name** uses `notificationConfiguration.name`, then optional `metadata.serverName` / `metadata.stackstateUrl`, then host from a URL.
- **Server URL** prefers `SUSE_OBS_BASE_URL` when set; otherwise the first non-empty link among `monitor.link`, `component.link`, `notificationConfiguration.link`.
- **Batching key** for `MONITORING_BATCH_ENABLED` is `monitor.identifier` when present, otherwise `monitor.name`. The **first** open in a cycle goes out immediately; only **subsequent** opens in the same window are summarized together. **Close** events are never batched.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
export MATTERMOST_URL="https://your-mattermost/hooks/your-key"
uvicorn suseobs_mattermost.app:create_app --factory --host 0.0.0.0 --port 8080
```

Or:

```bash
export MATTERMOST_URL="https://your-mattermost/hooks/your-key"
python -m suseobs_mattermost.main
```

Point SUSE Observability at `POST http://<host>:8080/webhook/suse-obs` with `Content-Type: application/json`.

## Tests

```bash
pytest
```

## Container image

```bash
docker build -t suseobs-mattermost:local .
docker run --rm -e MATTERMOST_URL -p 8080:8080 suseobs-mattermost:local
```

Image runs as non-root (`appuser`), exposes `8080`, sets `PYTHONUNBUFFERED=1`.

## Kubernetes

See [`examples/kubernetes-deployment.yaml`](examples/kubernetes-deployment.yaml) for probes on `/healthz` and `/readyz`, env from `ConfigMap` / `Secret`, and modest resource limits.

## CI

GitHub Actions runs **Ruff**, **pytest**, **pip-audit** on `requirements.txt`, builds the **Docker** image, scans it with **Trivy** (HIGH/CRITICAL, unfixed ignored), and pushes to **Docker Hub** as `erickuiper/suseobs-to-mattermost-webhook` on pushes to `main`.

Configure repository secrets **`DOCKERHUB_USERNAME`** and **`DOCKERHUB_TOKEN`** (Docker Hub access token).

**Releases:** Push a semver git tag `vX.Y.Z` to publish `X.Y.Z` and `latest` on Docker Hub; see [`docs/RELEASE.md`](docs/RELEASE.md). Use an explicit image tag (not only `latest`) in Kubernetes so rollouts pull the new image.
