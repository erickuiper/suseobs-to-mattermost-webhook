# Testing the webhook endpoint

The service accepts **POST** requests at **`/webhook/suse-obs`** with **`Content-Type: application/json`**.

Point SUSE Observability / StackState at this URL, or call it manually with **`curl`** (or any HTTP client).

## Base URL

| Environment | Example base URL |
|---------------|------------------|
| Local (default) | `http://127.0.0.1:8080` |
| Docker | `http://127.0.0.1:8080` (map container port `-p 8080:8080`) |
| Kubernetes | `https://<your-ingress-or-service>/` |

Full path: **`{base}/webhook/suse-obs`**

## Prerequisites

1. **`MATTERMOST_URL`** is set to a valid Mattermost **incoming webhook** URL (the service forwards the rendered message there).
2. For local runs, export at least:

   ```bash
   export MATTERMOST_URL='https://your-mattermost.example.com/hooks/your-incoming-webhook-key'
   ```

3. If Mattermost uses a **corporate or self-signed CA**, prefer pointing at a PEM bundle:

   ```bash
   export MATTERMOST_SSL_CA_BUNDLE=/path/to/your-ca.pem
   ```

   For quick local testing only, you can disable verification:

   ```bash
   export MATTERMOST_VERIFY_SSL=false
   ```

4. If **`WEBHOOK_AUTH_TOKEN`** is set, include one of:
   - `Authorization: Bearer <token>`
   - `X-Webhook-Token: <token>`
   - `X-StackState-Webhook-Token: <token>` (matches StackState’s OpenAPI security name)

## Sample payload (open event)

Taken from `spec/suse-obs.webhook-api.yaml`, with **`metadata`** added (required by the schema).

Save as `payload.json`:

```json
{
  "notificationId": "3e9992c3-f5a9-4c85-a0fb-f8730868cb66",
  "event": {
    "type": "open",
    "state": "CRITICAL",
    "title": "HTTP - response time is above 3 seconds",
    "triggeredTimeMs": 1701247920000
  },
  "monitor": {
    "name": "HTTP - response time",
    "identifier": "urn:stackpack:kubernetes-v2:shared:monitor:kubernetes-v2:http-response-time",
    "link": "https://stackstate.example.com/#/monitors/155483794918865",
    "tags": []
  },
  "component": {
    "identifier": "urn:endpoint:/customer.example.com:192.168.0.123",
    "link": "https://stackstate.example.com/#/components/urn:endpoint:%2Fcustomer.example.com:192.168.0.123",
    "name": "Kafka",
    "type": "service",
    "tags": ["customer=example_com"]
  },
  "notificationConfiguration": {
    "name": "example_com_webhook"
  },
  "metadata": {}
}
```

## curl

```bash
curl -sS -i \
  -X POST 'http://127.0.0.1:8080/webhook/suse-obs' \
  -H 'Content-Type: application/json' \
  --data-binary @payload.json
```

### With optional auth token

```bash
curl -sS -i \
  -X POST 'http://127.0.0.1:8080/webhook/suse-obs' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_SECRET' \
  --data-binary @payload.json
```

### Inline JSON (no file)

```bash
curl -sS -i \
  -X POST 'http://127.0.0.1:8080/webhook/suse-obs' \
  -H 'Content-Type: application/json' \
  -d '{"notificationId":"3e9992c3-f5a9-4c85-a0fb-f8730868cb66","event":{"type":"open","state":"CRITICAL","title":"Test","triggeredTimeMs":1701247920000},"monitor":{"name":"Mon","tags":[]},"component":{"identifier":"urn:x","link":"https://example.com/c","name":"Svc","type":"service","tags":[]},"notificationConfiguration":{"name":"nc"},"metadata":{}}'
```

## Expected responses

| HTTP | Meaning |
|------|---------|
| `200` | JSON accepted and Mattermost delivery succeeded (check Mattermost channel). |
| `400` | Invalid JSON or validation error (body does not match the StackState envelope). |
| `401` | `WEBHOOK_AUTH_TOKEN` is set but auth header is missing or wrong. |
| `415` | `Content-Type` is not `application/json`. |
| `502` | Mattermost returned an error or timed out. |

Successful body shape (example):

```json
{"status":"accepted","request_id":"<uuid>"}
```

## Health checks

```bash
curl -sS http://127.0.0.1:8080/healthz
curl -sS http://127.0.0.1:8080/readyz
curl -sS http://127.0.0.1:8080/version   # JSON: version (semver or 0.1.0+<sha>), git_sha
```

## Debug

Set **`LOG_LEVEL=DEBUG`** (see `.env.example`) to log request correlation, validation, and delivery details without leaking webhook secrets in the normal case.
