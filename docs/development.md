# Development Guide

This guide is for contributors working on the `cap-reference` codebase.

## Prerequisites

- Python 3.11 or newer
- `uv`
- access to an Abel gateway or a mock upstream for integration work

## Local Setup

Install dependencies:

```bash
make install
```

Create a local environment file:

```bash
make init-env
```

Start the development server:

```bash
make dev
```

Or use the Python entrypoint:

```bash
make run
```

## Common Commands

The `Makefile` exposes the main development tasks:

```bash
make help
make install
make init-env
make dev
make test
make test-verbose
make lint
make format
make check
```

`make check` runs lint plus tests.

## Repository Layout

The important directories are:

- `abel_cap_server/`
  - FastAPI server, adapters, service layer, gateway client, and Abel-specific contracts
- `abel_cap_client/`
  - example async CLI client that talks to the same CAP dispatch endpoint
- `tests/`
  - contract, adapter, configuration, and client-example coverage

Within `abel_cap_server/`, these files matter most when changing behavior:

- `main.py`
  - app assembly and shared state
- `api/meta.py`
  - `/` and `/.well-known/cap.json`
- `api/v1/endpoints/cap_dispatch.py`
  - single CAP entrypoint
- `cap/catalog.py`
  - verb registry and Capability Card metadata
- `cap/handlers.py`
  - request-bound handlers used by the dispatcher
- `cap/service.py`
  - stable service surface over the adapters
- `cap/adapters/`
  - public CAP-to-upstream translation
- `clients/abel_gateway_client.py`
  - gateway HTTP client

## Testing Strategy

The test suite is intentionally organized around public behavior:

- `tests/test_health.py`
  - service metadata and health routes
- `tests/test_config.py`
  - settings validation and required env vars
- `tests/test_cap_graph.py`
  - Capability Card exposure
  - CAP route behavior
  - adapter mapping
  - disclosure shaping
  - graph reference validation
  - header forwarding to the gateway
- `tests/test_cap_protocol_sdk.py`
  - integration expectations with the external `cap-protocol` package
  - builder defaults
  - registry and error-shaping behavior
- `tests/test_cap_client_example.py`
  - example client behavior and request payload shapes

Preferred validation commands:

```bash
uv run pytest -q tests/test_cap_protocol_sdk.py tests/test_cap_graph.py tests/test_health.py tests/test_config.py tests/test_cap_client_example.py
uv run python -m ruff check abel_cap_server tests abel_cap_client
```

## Development Principles

This repository should stay thin and boring.

That means:

- keep public HTTP contract logic here
- keep Abel-specific adapter logic here
- do not re-implement graph algorithms or causal compute semantics here
- do not spread gateway calls across route handlers
- keep public verb registration centralized in `abel_cap_server/cap/catalog.py`

If a change requires new computation semantics, implement that in the upstream compute layer first and then adapt it here.

## Typical Change Workflow

When adding or changing a CAP verb:

1. read the relevant CAP spec section first
2. confirm the behavior belongs in this wrapper rather than the upstream engine
3. add or update tests in `tests/`
4. update DTOs
   - protocol-generic DTOs belong in `cap-protocol`
   - Abel-only DTOs belong under `abel_cap_server/cap/contracts/extensions.py`
5. implement adapter logic in `abel_cap_server/cap/adapters/`
6. update or add upstream client calls in `abel_cap_server/clients/abel_gateway_client.py`
7. register the surface in `abel_cap_server/cap/catalog.py`
8. update documentation and examples

## Choosing The Right Layer

Use this rule of thumb:

- `cap-protocol`
  - reusable CAP contracts, envelopes, registry, and transport helpers
- `abel_cap_server/`
  - Abel-specific metadata, disclosure policy inputs, gateway calls, extensions, and response shaping
- upstream Abel compute layer
  - actual causal computation and internal schema semantics

If a field only makes sense for Abel, keep it out of the shared protocol package.

## Documentation Expectations

Any change to the public CAP surface should update:

- `README.md`
- `docs/api-reference.md`
- `docs/architecture.md` when the request flow or responsibility boundary changed
- `docs/configuration.md` when settings or auth behavior changed
- `CONTRIBUTING.md` when contributor workflow changed

The Capability Card is part of the public contract, so do not treat it as optional docs.

## Local Mocking Patterns

The existing tests use `httpx.MockTransport` heavily. That pattern is preferred for:

- gateway URL assertions
- authorization header forwarding tests
- adapter payload mapping checks

Use `fastapi.testclient.TestClient` for route-level tests and `MockTransport` for service or client-level tests.
