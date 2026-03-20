# Configuration

This document describes the runtime configuration exposed by `abel_cap_server.core.config.Settings`.

## Settings Source

Configuration is loaded through `pydantic-settings` with these rules:

- `.env` is loaded automatically when present
- environment variable prefix is `CAP_`
- environment names are case-insensitive
- unknown variables are ignored

The settings object is cached by `get_settings()`.

## Environment Variables

| Variable | Default | Required | Purpose |
| --- | --- | --- | --- |
| `CAP_APP_NAME` | `abel-cap` | no | FastAPI title and service metadata name |
| `CAP_APP_VERSION` | `0.1.0` | no | service version and Capability Card version |
| `CAP_APP_ENV` | `dev` | no | runtime environment label returned by `/api/v1/health` |
| `CAP_APP_HOST` | `0.0.0.0` | no | host used by the Python entrypoint |
| `CAP_APP_PORT` | `8000` | no | port used by the Python entrypoint |
| `CAP_API_V1_PREFIX` | `/api/v1` | no | versioned API prefix |
| `CAP_LOG_LEVEL` | `INFO` | no | application log level |
| `CAP_LOG_JSON` | `false` | no | enable structured JSON logs |
| `CAP_UPSTREAM_BASE_URL` | none | yes | base URL for Abel primitive gateway requests |
| `CAP_CAP_UPSTREAM_BASE_URL` | none | compatibility alias | alternate env name accepted for `cap_upstream_base_url` |
| `CAP_UPSTREAM_TIMEOUT_SECONDS` | `10.0` | no | default timeout for upstream gateway requests |
| `CAP_PROVIDER_NAME` | `Abel AI` | no | provider name shown in the Capability Card |
| `CAP_PROVIDER_URL` | `https://abel.ai` | no | provider URL shown in the Capability Card |
| `CAP_GATEWAY_API_KEY` | none | conditionally | fallback Bearer token for upstream gateway calls |

## Required Minimum Configuration

For local development or deployment, the smallest useful config is:

```bash
CAP_UPSTREAM_BASE_URL=https://example.invalid/api
CAP_GATEWAY_API_KEY=replace-with-your-gateway-api-key
```

`CAP_UPSTREAM_BASE_URL` has no built-in default. Startup fails validation if it is missing.

## Auth Header Resolution

The server itself advertises public HTTP access in the Capability Card, but upstream primitive calls may still need authorization.

`AbelGatewayClient` resolves authorization this way:

1. if the inbound request contains `Authorization`, forward that value upstream
2. otherwise use `CAP_GATEWAY_API_KEY`
3. normalize the value into `Bearer <token>` format

This lets a deployment choose between caller-supplied credentials and a server-side fallback credential.

## Timeout Behavior

Two timeout knobs are involved:

- `CAP_UPSTREAM_TIMEOUT_SECONDS`
  - default client timeout for all upstream requests
- `options.timeout_ms`
  - optional per-request timeout override forwarded from the CAP envelope

If the upstream request times out, the server returns CAP error code `computation_timeout`.

## Logging And Request IDs

Runtime logging behavior:

- `CAP_LOG_LEVEL` controls logger verbosity
- `CAP_LOG_JSON=true` enables JSON logs
- `RequestLoggingMiddleware` generates an `X-Request-ID` header when the caller does not provide one
- the same `X-Request-ID` is written back to the response headers

## Local `.env` Example

The repository ships `.env.example`:

```bash
CAP_APP_ENV=dev
CAP_APP_HOST=0.0.0.0
CAP_APP_PORT=8000
CAP_LOG_LEVEL=INFO
CAP_LOG_JSON=false
CAP_UPSTREAM_BASE_URL=https://example.invalid/api
CAP_UPSTREAM_TIMEOUT_SECONDS=10
CAP_PROVIDER_NAME=Abel AI
CAP_PROVIDER_URL=https://abel.ai
CAP_GATEWAY_API_KEY=replace-with-your-gateway-api-key
```

## Docker Notes

The Docker image:

- listens on port `8080`
- uses `uv sync --frozen --no-dev` at build time
- starts `uvicorn abel_cap_server.main:app --host 0.0.0.0 --port 8080`

Typical container run command:

```bash
docker run --rm -p 8080:8080 \
  -e CAP_UPSTREAM_BASE_URL=https://example.invalid/api \
  -e CAP_GATEWAY_API_KEY=replace-with-your-gateway-api-key \
  cap-reference
```

## Capability Card Impact

A few settings change public metadata directly:

- `CAP_APP_VERSION`
  - becomes the service version in `GET /` and `/.well-known/cap.json`
- `CAP_PROVIDER_NAME`
  - becomes `provider.name` in the Capability Card
- `CAP_PROVIDER_URL`
  - becomes `provider.url` in the Capability Card
- `CAP_API_V1_PREFIX`
  - changes the advertised CAP endpoint URL inside the Capability Card
