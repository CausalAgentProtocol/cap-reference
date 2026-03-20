# Architecture

This document explains how the `cap-reference` server is assembled, where behavior lives, and how a CAP request travels through the codebase.

## Design Goals

The service is intentionally thin:

- expose CAP over HTTP with one public dispatch endpoint
- publish a Capability Card at `/.well-known/cap.json`
- validate CAP request envelopes and route them by verb
- translate public CAP requests into Abel gateway primitive calls
- sanitize hidden fields before sending responses back to callers

The service is intentionally not:

- a second causal engine
- a place for new graph algorithms
- a place to expose internal graph facts that violate the public disclosure contract

## Runtime Assembly

App startup lives in `abel_cap_server/main.py`.

At startup the app:

1. loads `Settings`
2. configures logging
3. creates one shared `AbelGatewayClient`
4. creates one shared `CapService`
5. registers CAP exception handlers
6. installs `RequestLoggingMiddleware`
7. mounts the metadata router and the versioned API router

The gateway client and service are stored under `app.state`, which is why request handlers can stay small and stateless.

## Request Lifecycle

For `POST /api/v1/cap`, the code path is:

1. `abel_cap_server/api/v1/endpoints/cap_dispatch.py`
   - creates a dispatcher with `cap.server.build_fastapi_cap_dispatcher`
   - passes in the centralized registry from `abel_cap_server/cap/catalog.py`
   - passes in a provenance context provider from `abel_cap_server/cap/provenance.py`
2. `cap.server`
   - validates the CAP envelope
   - resolves `payload.verb` to a registered handler
   - normalizes request defaults such as `options.response_detail="summary"`
3. `abel_cap_server/cap/handlers.py`
   - reads `request.app.state.cap_service`
   - forwards the typed request model and incoming headers
4. `abel_cap_server/cap/service.py`
   - dispatches to the corresponding adapter function
5. `abel_cap_server/cap/adapters/*`
   - validates `context.graph_ref` if present
   - maps CAP params to upstream primitive payloads
   - forwards `timeout_ms` and headers
   - sanitizes hidden upstream fields
   - builds CAP-safe result DTOs and provenance hints
6. `abel_cap_server/clients/abel_gateway_client.py`
   - sends HTTP requests to the configured Abel gateway base URL
   - forwards caller `Authorization` when present
   - otherwise falls back to `CAP_GATEWAY_API_KEY`
7. `cap.server`
   - wraps adapter output into a CAP success envelope
   - adds provenance from the service-level context and the adapter hint

## Metadata Endpoints

Two routes live outside the versioned API dispatch path:

- `GET /`
  - implemented in `abel_cap_server/api/meta.py`
  - returns service name, version, docs, and OpenAPI paths
- `GET /.well-known/cap.json`
  - also implemented in `abel_cap_server/api/meta.py`
  - calls `CapService.build_capability_card`

The `meta.capabilities` verb returns the same Capability Card payload as `/.well-known/cap.json`.

## Component Responsibilities

The main modules are divided like this:

- `abel_cap_server/main.py`
  - application assembly and shared dependency wiring
- `abel_cap_server/api/meta.py`
  - root metadata and well-known Capability Card route
- `abel_cap_server/api/v1/endpoints/cap_dispatch.py`
  - unified CAP HTTP entrypoint
- `abel_cap_server/cap/catalog.py`
  - public verb registry
  - graph/profile metadata
  - extension namespace metadata
  - Capability Card assembly
- `abel_cap_server/cap/handlers.py`
  - request-scoped handler functions used by the dispatcher
- `abel_cap_server/cap/service.py`
  - stable service API that adapters call through
- `abel_cap_server/cap/adapters/`
  - request validation
  - upstream payload shaping
  - response sanitization
  - CAP result modeling
- `abel_cap_server/clients/abel_gateway_client.py`
  - all outbound HTTP to Abel gateway primitives
- `abel_cap_server/cap/disclosure.py`
  - forbidden field list and assumption sets
- `abel_cap_server/cap/errors.py`
  - upstream-to-CAP error translation policy
- `abel_cap_server/cap/provenance.py`
  - server provenance context used in CAP responses

## Registry And Capability Card

`abel_cap_server/cap/catalog.py` is the single source of truth for the public surface.

It defines:

- the centralized `CAPVerbRegistry`
- all core, convenience, and extension verb registrations
- the default graph profile
- Abel extension metadata
- disclosure notes and access tier metadata
- Capability Card assembly

This matters because the Capability Card should reflect the actual registered surface, not a hand-maintained second list somewhere else in the project.

## Upstream Mapping

The adapter layer maps CAP verbs to Abel primitive endpoints:

- `observe.predict`
  - upstream call: `POST {base}/v1/predict`
  - adapter adds `model="linear"` and `feature_type="parents"`
- `intervene.do`
  - upstream call: `POST {base}/v1/intervene`
  - adapter adds `model="linear"` and `horizon_steps=24`
  - public result is intentionally smaller than the raw upstream payload
- `graph.neighbors`
  - upstream call: `POST {base}/v1/explain`
  - adapter sets `scope` to `parents` or `children`
- `graph.markov_blanket`
  - upstream call: `POST {base}/v1/explain`
  - adapter sets `scope="markov_blanket"`
- `graph.paths`
  - upstream call: `GET {base}/v1/schema/paths?from=...&to=...`
- `traverse.parents`
  - upstream call: `POST {base}/v1/explain`
  - adapter sets `scope="parents"`
- `traverse.children`
  - upstream call: `POST {base}/v1/explain`
  - adapter sets `scope="children"`
- `extensions.abel.validate_connectivity`
  - upstream call: `POST {base}/v1/validate`
  - adapter adds `validation_mode="iv_gate"`
- `extensions.abel.markov_blanket`
  - upstream call: `POST {base}/v1/explain`
  - adapter converts markov blanket neighbors into Abel extension fields
- `extensions.abel.counterfactual_preview`
  - upstream call: `POST {base}/v1/counterfactual`
  - adapter adds `model="linear"`
  - public result is explicitly marked as preview-only
- `extensions.abel.intervene_time_lag`
  - upstream call: `POST {base}/v1/intervene`
  - requires `model="linear"`
  - preserves richer time-lag summaries than core `intervene.do`

## Disclosure Policy

The disclosure contract is enforced in code, not only in documentation.

`abel_cap_server/cap/disclosure.py` defines `FORBIDDEN_FIELDS`:

- `weight`
- `tau`
- `conditioning_set`
- `p_value`
- `confidence_interval`
- `ci_lower`
- `ci_upper`

Adapters sanitize raw upstream payloads through `sanitize_hidden_fields` before building public DTOs.

The Capability Card also advertises:

- default response detail: `summary`
- public access tier only
- the same hidden-field policy

## Graph Compatibility Guardrails

If a request provides `context.graph_ref`, the adapter layer accepts only:

- `graph_id="abel-main"`
- `graph_version="CausalNodeV2"`

If the request omits `graph_ref`, the server proceeds with its default graph profile.

This check is centralized in `abel_cap_server/cap/adapters/common.py`.

## Provenance

Every CAP response may include provenance assembled from two sources:

- service-level context from `abel_cap_server/cap/provenance.py`
  - graph version
  - server name
  - server version
- adapter-level hints
  - algorithm name such as `primitive.predict`, `primitive.explain`, or `PCMCI`
  - mechanism family when relevant

This keeps route handlers free from manual provenance assembly.

## Header And Request ID Behavior

Two runtime behaviors are easy to miss:

- `Authorization`
  - forwarded upstream when the inbound request includes it
  - otherwise built from `CAP_GATEWAY_API_KEY`
- `X-Request-ID`
  - generated by `RequestLoggingMiddleware` when absent
  - echoed back on the HTTP response
  - used in request-scoped logging context

## Error Translation

`abel_cap_server/cap/errors.py` converts upstream failures into CAP-shaped errors.

Current policy:

- upstream timeout -> `computation_timeout` with HTTP 504
- upstream 404 -> `node_not_found` or `path_not_found`
- upstream 400/422 -> `invalid_request` or `invalid_intervention`
- upstream 503 or transport errors -> `service_unavailable`
- everything else -> `upstream_error`

## How To Extend The Surface

If you need to add a new public CAP verb, follow this path:

1. confirm the capability belongs in the thin wrapper instead of the upstream compute layer
2. add or update tests under `tests/`
3. add protocol-generic DTOs in `cap-protocol`, or Abel-only DTOs under `abel_cap_server/cap/contracts/extensions.py`
4. implement adapter logic under `abel_cap_server/cap/adapters/`
5. register the verb in `abel_cap_server/cap/catalog.py`
6. add or update upstream client methods in `abel_cap_server/clients/abel_gateway_client.py`
7. update `docs/api-reference.md`, `README.md`, and the Capability Card metadata if the public surface changed

More contributor workflow details live in `docs/development.md`.
