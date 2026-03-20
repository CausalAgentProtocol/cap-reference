# cap-reference

Reference CAP server implementation for the Causal Agent Protocol (CAP).

If you are new to CAP, start with the [`cap` repository](https://github.com/CausalAgentProtocol/cap) for the protocol overview, getting-started guides, and normative specification. This repository is for people who want to inspect a working CAP server and understand how capability disclosure, CAP envelope dispatch, and implementation-specific extensions look in practice.

## Choose The Right Repo

- [`cap`](https://github.com/CausalAgentProtocol/cap): learn CAP and read the authoritative protocol docs
- [`python-sdk`](https://github.com/CausalAgentProtocol/python-sdk): build CAP clients and CAP-compatible Python services
- [`cap-reference`](https://github.com/CausalAgentProtocol/cap-reference): study a running reference server that exposes CAP over HTTP

## What This Repository Demonstrates

The current codebase shows a concrete CAP server that:

- publishes a machine-readable capability card at `/.well-known/cap.json`
- exposes CAP through a single HTTP entrypoint at `POST /api/v1/cap`
- dispatches requests by CAP `verb`, not by one-route-per-verb HTTP design
- separates CAP core and convenience verbs from Abel-specific extension verbs
- applies disclosure policy before returning protocol responses

This server is intentionally narrow. It is an adapter over Abel-backed primitives, not the CAP standard itself and not a full causal engine implementation.

## What To Look At First

Use this repository to understand three CAP ideas in a running service:

1. Capability disclosure before invocation.
2. A single CAP envelope surface over HTTP.
3. The boundary between CAP core behavior and implementation-specific extensions.

The best entry points for that are:

- `GET /.well-known/cap.json`
- `POST /api/v1/cap`
- [`abel_cap_server/cap/catalog.py`](abel_cap_server/cap/catalog.py)

## Run It Locally

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

Then inspect:

- `http://127.0.0.1:8000/.well-known/cap.json`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/v1/health`

Minimal required configuration:

```bash
CAP_UPSTREAM_BASE_URL=https://example.invalid/api
CAP_GATEWAY_API_KEY=replace-with-your-gateway-api-key
```

`CAP_UPSTREAM_BASE_URL` is required. Defaults and the full configuration surface are documented in [`docs/configuration.md`](docs/configuration.md) and implemented in `abel_cap_server/core/config.py`.

## Try The CAP Surface

Fetch capabilities first:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-capabilities-1",
    "verb": "meta.capabilities"
  }' | jq
```

Query graph neighbors:

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

Run a core intervention:

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

If you want the full verb-by-verb HTTP details, use [`docs/api-reference.md`](docs/api-reference.md).

## Current Server Surface

The current dispatch registry exposes:

- core verbs: `meta.capabilities`, `observe.predict`, `intervene.do`, `graph.neighbors`, `graph.markov_blanket`, `graph.paths`
- convenience verbs: `traverse.parents`, `traverse.children`
- Abel extensions: `extensions.abel.validate_connectivity`, `extensions.abel.markov_blanket`, `extensions.abel.counterfactual_preview`, `extensions.abel.intervene_time_lag`

The capability card currently describes this service as a Level 2 CAP adapter over Abel primitives. In the current implementation, `intervene.do` uses the server's default linear SCM rollout over the public time-lagged graph, while richer or more product-specific behavior remains in the `extensions.abel.*` namespace.

## Why The Core Vs Extension Boundary Matters

This repository is useful because it keeps the protocol boundary explicit:

- CAP core behavior is exposed through the standard verb surface and capability disclosure
- convenience verbs stay visible without pretending to redefine the protocol
- Abel-specific behavior is namespaced under `extensions.abel.*` instead of being relabeled as CAP core

That is one of the main things a reference implementation should teach.

## Repository Docs

Use repo-local docs for implementation and contributor detail:

- [`docs/architecture.md`](docs/architecture.md): runtime assembly, request flow, gateway mapping, disclosure policy
- [`docs/api-reference.md`](docs/api-reference.md): endpoints, CAP envelope shape, supported verbs, error behavior
- [`docs/configuration.md`](docs/configuration.md): environment variables, auth header behavior, deployment notes
- [`docs/development.md`](docs/development.md): local setup, test strategy, change workflow

## Example Client

The repository includes a small demo CLI in [`abel_cap_client/`](abel_cap_client/). It talks to the same unified `POST /api/v1/cap` endpoint.

```bash
uv run python -m abel_cap_client --base-url http://127.0.0.1:8000 capabilities
```

Use it as a demo client for this server. For reusable Python integration across CAP services, use the official [`python-sdk`](https://github.com/CausalAgentProtocol/python-sdk).

## Contributing And Community

Use repo-local docs for repo-specific workflow:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SECURITY.md`](SECURITY.md)

Use CAP organization docs for shared community policy:

- [Org-wide Contributing Guide](https://github.com/CausalAgentProtocol/.github/blob/main/CONTRIBUTING.md)
- [Org-wide Code of Conduct](https://github.com/CausalAgentProtocol/.github/blob/main/CODE_OF_CONDUCT.md)

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
