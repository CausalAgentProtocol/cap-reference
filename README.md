# cap-reference

Thin FastAPI reference server for the Causal Agent Protocol (CAP) v0.2.2.

`cap-reference` is the open-source HTTP wrapper around Abel-backed CAP primitives. It exposes a single CAP dispatch endpoint, serves a Capability Card, validates CAP envelopes, applies disclosure policy, and proxies execution to the upstream Abel gateway. It does not implement causal computation itself.

## Why This Repo Exists

This repository owns the public CAP HTTP surface:

- `GET /`
- `GET /.well-known/cap.json`
- `GET /api/v1/health`
- `POST /api/v1/cap`

It also owns Abel-specific adapter behavior:

- request-to-upstream mapping
- public response shaping
- disclosure-safe field sanitization
- provenance metadata
- Abel extension contracts

It does not own:

- graph math or graph search implementations
- prediction, intervention, or counterfactual engine internals
- hidden graph statistics such as weights, taus, conditioning sets, or confidence intervals

## Documentation

- [`docs/architecture.md`](docs/architecture.md): runtime assembly, request flow, gateway mapping, disclosure policy
- [`docs/api-reference.md`](docs/api-reference.md): HTTP endpoints, CAP envelope shape, supported verbs, error behavior
- [`docs/configuration.md`](docs/configuration.md): environment variables, auth header behavior, deployment notes
- [`docs/development.md`](docs/development.md): local setup, test strategy, change workflow
- [`CONTRIBUTING.md`](CONTRIBUTING.md): branch, commit, PR, and review expectations
- [`SECURITY.md`](SECURITY.md): security reporting and secret-handling guidance

## Public Surface

HTTP endpoints:

- `GET /`
  - service metadata and docs links
- `GET /.well-known/cap.json`
  - Capability Card built from the centralized registry
- `GET /api/v1/health`
  - health status, app name, environment, version
- `POST /api/v1/cap`
  - unified CAP entrypoint that dispatches by `payload.verb`

Supported verbs:

- Core
  - `meta.capabilities`
  - `observe.predict`
  - `intervene.do`
  - `graph.neighbors`
  - `graph.markov_blanket`
  - `graph.paths`
- Convenience
  - `traverse.parents`
  - `traverse.children`
- Abel extensions
  - `extensions.abel.validate_connectivity`
  - `extensions.abel.markov_blanket`
  - `extensions.abel.counterfactual_preview`
  - `extensions.abel.intervene_time_lag`

## Architecture Summary

The runtime flow stays intentionally thin:

1. [`abel_cap_server/main.py`](abel_cap_server/main.py) creates the FastAPI app, settings, gateway client, CAP service, exception handlers, and request logging middleware.
2. [`abel_cap_server/api/v1/endpoints/cap_dispatch.py`](abel_cap_server/api/v1/endpoints/cap_dispatch.py) hands `POST /api/v1/cap` to `cap.server.build_fastapi_cap_dispatcher`.
3. [`abel_cap_server/cap/catalog.py`](abel_cap_server/cap/catalog.py) keeps all public verb registration and Capability Card metadata in one place.
4. [`abel_cap_server/cap/handlers.py`](abel_cap_server/cap/handlers.py) resolves `CapService` from `request.app.state`.
5. [`abel_cap_server/cap/service.py`](abel_cap_server/cap/service.py) delegates each verb to an adapter.
6. [`abel_cap_server/cap/adapters/`](abel_cap_server/cap/adapters/) validates graph compatibility, shapes upstream payloads, sanitizes hidden fields, and returns CAP-safe DTOs.
7. [`abel_cap_server/clients/abel_gateway_client.py`](abel_cap_server/clients/abel_gateway_client.py) sends gateway requests to Abel primitive endpoints.

The most important boundary: causal computation stays upstream. This server only exposes and constrains the public HTTP contract.

## Quick Start

Prerequisites:

- Python 3.11+
- `uv`

Install and run locally:

```bash
make install
make init-env
make dev
```

Or run directly:

```bash
uv sync --extra dev
cp .env.example .env
uv run uvicorn abel_cap_server.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`
- `http://127.0.0.1:8000/.well-known/cap.json`

Minimal required configuration:

```bash
CAP_UPSTREAM_BASE_URL=https://example.invalid/api
CAP_GATEWAY_API_KEY=replace-with-your-gateway-api-key
```

`CAP_UPSTREAM_BASE_URL` is required. The server does not ship a default upstream base URL.

## Example Requests

Fetch the Capability Card through CAP itself:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-capabilities-1",
    "verb": "meta.capabilities"
  }' | jq
```

Query structural neighbors:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-neighbors-1",
    "verb": "graph.neighbors",
    "params": {
      "node_id": "NVDA_close",
      "scope": "parents",
      "max_neighbors": 5
    }
  }' | jq
```

Run an intervention through the core surface:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-intervene-1",
    "verb": "intervene.do",
    "params": {
      "treatment_node": "DXY_close",
      "treatment_value": 1.0,
      "outcome_node": "BTCUSD_close"
    }
  }' | jq
```

Call an Abel extension:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-validate-1",
    "verb": "extensions.abel.validate_connectivity",
    "params": {
      "variables": ["NVDA_close", "AAPL_close", "DXY_close"]
    }
  }' | jq
```

More verb-by-verb details live in [`docs/api-reference.md`](docs/api-reference.md).

## Example Client

The repository includes a tiny example CLI in [`abel_cap_client/`](abel_cap_client/). It still talks to the same unified `POST /api/v1/cap` endpoint.

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 capabilities
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 --header "Authorization: Bearer your-token" capabilities
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 neighbors NVDA_close --scope parents --max-neighbors 5
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 observe BTCUSD_volume
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 markov-blanket NVDA_close --max-neighbors 10
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 intervene-time-lag NVDA_close 0.05 --outcome-node SONY_close --horizon-steps 24 --model linear
```

Pass auth explicitly as a request header, for example `--header "Authorization: Bearer your-token"`. You can repeat `--header "Name: Value"` for custom headers such as `X-Trace-ID`. If you omit `Authorization` entirely, the server can still fall back to its `CAP_GATEWAY_API_KEY` configuration.

## Docker

Build and run:

```bash
docker build -t cap-reference .
docker run --rm -p 8080:8080 \
  -e CAP_UPSTREAM_BASE_URL=https://example.invalid/api \
  -e CAP_GATEWAY_API_KEY=replace-with-your-gateway-api-key \
  cap-reference
```

The container starts:

```bash
uv run --no-sync uvicorn abel_cap_server.main:app --host 0.0.0.0 --port 8080
```

## Development

Common commands:

```bash
make install
make init-env
make dev
make test
make lint
make check
```

The main local validation set is:

```bash
uv run pytest -q tests/test_cap_protocol_sdk.py tests/test_cap_graph.py tests/test_health.py tests/test_config.py tests/test_cap_client_example.py
uv run python -m ruff check abel_cap_server tests abel_cap_client
```

Detailed contributor workflow lives in [`docs/development.md`](docs/development.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Contributing

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a branch or PR. The short version:

- keep the server thin
- do not re-implement Abel compute behavior here
- add tests before or alongside behavior changes
- keep registry wiring centralized in `abel_cap_server/cap/catalog.py`
- update docs whenever the public CAP surface changes

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
