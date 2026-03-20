# AGENTS.md

Instructions for coding agents working in this repository.

仓库外可能存在 CAP spec draft 或对齐文档，可以作为参考但不是唯一真理。

## 1) Purpose

- This repository is the open-source CAP HTTP reference wrapper.
- It is not the powerful closed-source causal engine. The upstream Abel compute layer remains the capability layer.
- This service should stay thin: define public CAP contracts, expose a Capability Card, validate/shape requests, and proxy to Abel services through the gateway.
- Do not re-implement graph math, path search, prediction logic, or causal semantics that already belong to the closed-source Abel compute layer.
- Before creating commits in this repository, read `CONTRIBUTING.md` and follow its commit / branch conventions.

## 2) Architecture Boundary

Keep this separation explicit:

- This repository
  - Public-facing CAP HTTP binding
  - Capability Card at `/.well-known/cap.json`
  - CAP response envelopes
  - Disclosure-policy enforcement for public responses
  - Gateway-aware upstream client code
- `cap-protocol` package (`cap.core`, `cap.client`, `cap.server`)
  - Reusable CAP contracts, envelopes, Capability Card models, client, registry, and FastAPI/server glue
  - No Abel-specific gateway paths, disclosure defaults, graph profiles, or extension payload semantics
- `abel_cap_server/`
  - Abel-backed HTTP server assembly, gateway client, adapter mapping, disclosure inputs, graph/profile metadata, and Abel extension contracts
- Upstream Abel compute layer
  - Real graph traversal and causal computation
  - Internal schema and computation surfaces
  - Internal/high-detail graph facts

If a change requires new causal computation or new graph query semantics, implement it in the upstream compute implementation first, then wrap it here.

## 3) Current CAP Surface

Start here before changing anything:

- `abel_cap_server/main.py`
  - App assembly and shared service/client wiring
- `abel_cap_server/api/meta.py`
  - Root metadata and `/.well-known/cap.json`
- `abel_cap_server/api/v1/endpoints/cap_dispatch.py`
  - Unified CAP entrypoint `POST /api/v1/cap`
  - Dispatches by payload `verb` through `cap.server.build_fastapi_cap_dispatcher`
- `abel_cap_server/cap/handlers.py`
  - Request-driven handlers that resolve `CapService` from `request.app.state.cap_service`
- `abel_cap_server/cap/catalog.py`
  - Single public catalog for registry wiring, supported verbs, graph/profile metadata, extension metadata, and Capability Card assembly
- `abel_cap_server/cap/contracts/__init__.py`
  - Abel-side compatibility re-exports for CAP DTOs plus Abel extension DTO access
- `abel_cap_server/cap/service.py`
  - CAP verb dispatch surface; keep service behavior here and public surface metadata in `catalog.py`
- `abel_cap_server/cap/adapters/`
  - CAP-to-primitive mapping and disclosure shaping
- `abel_cap_server/cap/errors.py`
  - Abel-specific upstream error translation policy; protocol-side adapter error class/handler glue lives under `cap.server`
- `cap.server`
  - Protocol-owned registry / FastAPI dispatch / error glue / success response helpers from the external `cap-protocol` dependency
- `cap.core.disclosure`
  - Protocol-owned field sanitization primitive; app layer keeps only Abel policy inputs
- `abel_cap_server/clients/abel_gateway_client.py`
  - Gateway HTTP client for upstream primitive calls
- `tests/test_cap_graph.py`
  - Primary contract tests for CAP endpoints and adapter behavior

## 4) How To Add A New Interface

When adding a new CAP endpoint, follow this order:

1. Read the relevant CAP spec section first.
   - Start from the repository's CAP protocol and product-positioning documentation
2. Confirm whether the capability belongs in this service at all.
   - If it is a public CAP verb wrapper, add it here
   - If it is upstream-only schema or computation, keep it in the upstream compute implementation
3. Add or update tests first in `tests/`.
   - Contract tests for route shape
   - Service mapping tests for upstream-to-public translation
   - Header passthrough tests if gateway calls are involved
4. Add or update DTOs in the external `cap-protocol` package when the contract is protocol-generic, or in `abel_cap_server/cap/contracts/extensions.py` when it is Abel-specific.
5. Add or update adapter logic in `abel_cap_server/cap/adapters/`.
6. Add or update shared registry wiring in `abel_cap_server/cap/catalog.py`. Prefer one-line registration there, e.g. `registry.core(CONTRACT)(handler)` or `registry.extension(...)(handler)`.
7. Add or update upstream HTTP client calls in `abel_cap_server/clients/abel_gateway_client.py`.
8. Wire the route in `abel_cap_server/api/v1/endpoints/` and `abel_cap_server/api/v1/router.py`.
9. Update the Capability Card if the public surface changed, but derive verb surface from registry metadata rather than hand-maintaining a second list.
10. Update README and any plan docs if the contract changed.

## 5) Request Shape Rules

- CAP endpoints in `abel_cap_server/api/v1` use CAP envelopes in the body (`cap_version`, `request_id`, `verb`, `params`, optional `options`).
- Unified route entrypoint is `POST /api/v1/cap`; `verb` determines which CAP method executes.
- Keep `params` minimal and explicit; do not expose raw upstream/internal schema fields.
- Responses use CAP envelopes (`cap_version`, `request_id`, `verb`, `status`, `result`, optional `provenance`).

Examples:

- Good:
  - `POST /api/v1/cap` with body `{ "cap_version": "0.2.2", "verb": "graph.neighbors", "params": { "node_id": "...", "scope": "parents", "max_neighbors": 3 } }`
- Avoid:
  - ad-hoc payloads that bypass the CAP envelope contract

## 6) Gateway Rules

This service must call Abel through the configured gateway CAP base URL, not directly to the compute layer.

Implementation rules:

- Put gateway HTTP calls in `abel_cap_server/clients/abel_gateway_client.py`
- Read the base URL from `Settings.cap_upstream_base_url`
- Use the server-side `CAP_GATEWAY_API_KEY` and send it upstream as `Authorization: Bearer {api-key}`
- Do not hardcode ad-hoc alternate upstream paths in endpoint modules
- Keep all header passthrough logic in one place if possible

Current upstream mapping:

- `observe.predict` → `POST {base}/v1/predict`
- `observe.predict` → `POST {base}/v1/predict`
- `intervene.do` → `POST {base}/v1/intervene`
- `graph.neighbors` and `traverse.*` → `POST {base}/v1/explain`
- `graph.paths` → `GET {base}/v1/schema/paths`
- `extensions.abel.validate_connectivity` → `POST {base}/v1/validate`
- `extensions.abel.counterfactual_preview` → `POST {base}/v1/counterfactual`

If a new CAP endpoint needs a new upstream schema or compute surface, add that surface in the upstream compute implementation first, then wire the client here.

## 7) Disclosure Policy Rules

This open-source wrapper must enforce the public disclosure contract, even though the code is visible.

Current disclosure policy is hidden-field based:

- Strip hidden fields listed in `abel_cap_server/cap/disclosure.py` (`FORBIDDEN_FIELDS`)
- Keep CAP responses summary-safe by default
- Do not expose raw internal statistics or confidence internals

Apply it in code, not only in the Capability Card:

- Sanitize upstream payloads via the adapter helper / `sanitize_hidden_fields` path in `abel_cap_server/cap/adapters/`
- Keep CAP core DTOs in `cap.core.contracts` and Abel-only DTOs in `abel_cap_server/cap/contracts/extensions.py`
- Do not leak raw internal summaries not part of the public CAP contract

If disclosure behavior changes, update:

1. `CapabilityCard.disclosure_policy`
2. route/service tests
3. README examples or notes

## 8) Capability Card Rules

The Capability Card is part of the public contract, not a docs afterthought.

Whenever you add, remove, or materially change a public verb:

- Update `/.well-known/cap.json` output in `abel_cap_server/api/meta.py` via `CapService.build_capability_card` (`abel_cap_server/cap/catalog.py`)
- Update the registry wiring in `abel_cap_server/cap/catalog.py`; the capability card verb surface should fall out of that registry automatically
- Keep `POST /api/v1/cap` with `verb=meta.capabilities` semantically equivalent to the well-known card
- Re-check:
  - `supported_verbs`
  - `conformance_level`
  - `authentication`
  - `graph` metadata
  - `disclosure_policy`
  - `causal_engine` / `detailed_capabilities` honesty
  - `bindings` only when MCP or A2A are actually exposed

Do not claim stronger CAP conformance than the implemented public surface supports.

## 9) Testing And Validation

Preferred local validation:

```bash
./.venv/bin/python -m pytest -q tests/test_cap_protocol_sdk.py tests/test_cap_graph.py tests/test_health.py tests/test_config.py
uv run python -m ruff check abel_cap_server tests abel_cap_client
```

For route smoke tests, use `TestClient` or `curl` with `Authorization: Bearer <api-key>`.

When gateway behavior changes, test both:

- route-level header passthrough
- service/client-level upstream URL construction

## 10) Simplicity Rules

- Keep this service thin and boring.
- Favor a small client + service + schema stack over spreading gateway logic through route handlers.
- Avoid speculative abstraction for verbs that do not exist yet.
- If you notice logic moving toward a second causal engine implementation here, stop and push that behavior back to the upstream compute implementation.
