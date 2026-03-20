# cap-reference

Thin FastAPI reference server for the Causal Agent Protocol (CAP) v0.2.2.

This repo has two local parts plus one external dependency:

- `abel_cap_server/`: the reference CAP server
- `abel_cap_client/`: tiny example CLI using `cap.client`
- `cap-protocol`: PyPI dependency that provides `cap.core`, `cap.client`, and `cap.server`

The server is intentionally narrow. It exposes CAP over HTTP, serves a Capability Card, enforces disclosure policy, and proxies to an upstream Abel service. It does not implement causal computation itself.

## Public Surface

- `GET /`
  - service metadata
- `GET /.well-known/cap.json`
  - Capability Card
- `GET /api/v1/health`
  - health check
- `POST /api/v1/cap`
  - single CAP entrypoint; dispatches by request `verb`

Supported verbs today:

- Core
  - `meta.capabilities`
  - `observe.predict`
  - `intervene.do`
  - `graph.neighbors`
  - `graph.paths`
- Convenience
  - `traverse.parents`
  - `traverse.children`
- Extensions
  - `extensions.abel.validate_connectivity`
  - `extensions.abel.markov_blanket`
  - `extensions.abel.counterfactual_preview`
  - `extensions.abel.intervene_time_lag`

`intervene.do` is now the smaller core intervention surface. Richer temporal propagation payload stays available through `extensions.abel.intervene_time_lag`.

## Repo Shape

Start here if you are changing behavior:

- `abel_cap_server/main.py`
  - app assembly and shared wiring
- `abel_cap_server/api/meta.py`
  - `/` and `/.well-known/cap.json`
- `abel_cap_server/api/v1/endpoints/cap_dispatch.py`
  - `POST /api/v1/cap`
- `abel_cap_server/cap/catalog.py`
  - public verb catalog, dispatch registry, graph metadata, Capability Card assembly
- `abel_cap_server/cap/handlers.py`
  - request-driven verb handlers that resolve `CapService` from `request.app.state`
- `abel_cap_server/cap/service.py`
  - service methods that adapters call through
- `abel_cap_server/cap/adapters/`
  - CAP-to-upstream mapping
- `abel_cap_server/clients/abel_gateway_client.py`
  - outbound HTTP to Abel
- `cap-protocol` (`cap.core`, `cap.server`)
  - shared CAP contracts, builders, envelopes, Capability Card models, registry, and dispatch helpers

Boundary rule of thumb:

- `cap-protocol` defines reusable CAP protocol primitives and transport glue
- `abel_cap_server/` defines Abel-specific metadata, disclosure policy, gateway calls, adapters, and extensions
- if a field or behavior would only make sense for Abel, keep it out of the shared `cap` package

## Quick Start

```bash
uv sync --extra dev
cp .env.example .env
uv run uvicorn abel_cap_server.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/.well-known/cap.json`

## Docker

Build and run:

```bash
docker build -t cap-reference .
docker run --rm -p 8080:8080 \
  -e CAP_UPSTREAM_BASE_URL=https://example.invalid/api/cap \
  -e CAP_GATEWAY_API_KEY=<your_api_key> \
  cap-reference
```

```bash
uv run --no-sync uvicorn abel_cap_server.main:app --host 0.0.0.0 --port 8080
```

## Config

Minimal local config:

```bash
CAP_APP_ENV=dev
CAP_LOG_JSON=false
CAP_UPSTREAM_BASE_URL=https://example.invalid/api
CAP_GATEWAY_API_KEY=<your_api_key>
```

Defaults live in `abel_cap_server/core/config.py`.

## Example Requests

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

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-observe-1",
    "verb": "observe.predict",
    "params": {
      "target_node": "BTCUSD_volume"
    }
  }' | jq
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-paths-1",
    "verb": "graph.paths",
    "params": {
      "source_node_id": "NVDA_close",
      "target_node_id": "SONY_close",
      "max_paths": 2
    }
  }' | jq
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-effect-1",
    "verb": "intervene.do",
    "params": {
      "treatment_node": "DXY_close",
      "treatment_value": 1.0,
      "outcome_node": "BTCUSD_close"
    }
  }' | jq
```

## Example Client Calls

The example CLI still posts to `POST /api/v1/cap`, including Abel extensions. Route-style aliases are resolved client-side before dispatch.

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 capabilities
```

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 neighbors NVDA_close --scope parents --max-neighbors 5
```

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 paths NVDA_close SONY_close --max-paths 2
```

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 observe BTCUSD_volume
```

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 markov-blanket NVDA_close --max-neighbors 10
```

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 intervene-time-lag NVDA_close 0.05 --outcome-node SONY_close --horizon-steps 24 --model linear
```

## Development

```bash
uv run pytest -q tests/test_cap_protocol_sdk.py tests/test_cap_graph.py tests/test_health.py tests/test_config.py tests/test_cap_client_example.py
uv run python -m ruff check abel_cap_server tests abel_cap_client
```

Contribution conventions are in `CONTRIBUTING.md`.
