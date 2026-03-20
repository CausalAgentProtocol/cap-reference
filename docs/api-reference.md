# API Reference

This document describes the public HTTP surface exposed by `cap-reference` and how each supported CAP verb maps onto the current code.

## Base URLs

By default the server runs at:

- local development: `http://127.0.0.1:8000`
- Docker image: `http://127.0.0.1:8080`

The canonical CAP invocation path is `/cap`.

## HTTP Endpoints

- `GET /`
  - returns service metadata
  - response fields: `name`, `version`, `docs`, `openapi`
- `GET /.well-known/cap.json`
  - returns the public Capability Card
- `GET /health`
  - returns `status`, `app_name`, `environment`, `version`
- `POST /cap`
  - accepts a CAP request envelope
  - dispatches by `verb`

## CAP Request Envelope

All CAP calls use the same JSON envelope:

```json
{
  "cap_version": "0.2.2",
  "request_id": "req-neighbors-1",
  "verb": "graph.neighbors",
  "params": {
    "node_id": "NVDA_close",
    "scope": "parents",
    "max_neighbors": 5
  },
  "options": {
    "response_detail": "summary",
    "timeout_ms": 1200
  },
  "context": {
    "graph_ref": {
      "graph_id": "abel-main",
      "graph_version": "CausalNodeV2"
    }
  }
}
```

Envelope rules:

- `cap_version` should be `0.2.2`
- `verb` selects the handler
- `params` depends on the verb
- `request_id` is optional but recommended
- `options.timeout_ms` is forwarded to the upstream gateway request
- `options.response_detail` defaults to `summary`
- `context.graph_ref` is optional, but if present it must match the server's supported graph identity

## CAP Success Envelope

Successful responses follow the standard CAP shape:

```json
{
  "cap_version": "0.2.2",
  "request_id": "req-neighbors-1",
  "verb": "graph.neighbors",
  "status": "success",
  "result": {},
  "provenance": {
    "algorithm": "primitive.explain",
    "graph_version": "CausalNodeV2",
    "server_name": "abel-cap",
    "server_version": "0.1.0",
    "cap_spec_version": "0.2.2"
  }
}
```

## Supported Verbs

### Core Verbs

- `meta.capabilities`
  - params: none
  - behavior: returns the same Capability Card as `GET /.well-known/cap.json`
  - implementation: `abel_cap_server/cap/handlers.py` and `abel_cap_server/cap/service.py`

- `observe.predict`
  - params:
    - `target_node`
  - upstream mapping:
    - `POST {base}/v1/predict`
    - adapter forces `model="linear"` and `feature_type="parents"`
  - result fields:
    - `target_node`
    - `prediction`
    - `drivers`
  - notes:
    - response is sanitized before shaping
    - provenance algorithm is `primitive.predict`

- `intervene.do`
  - params:
    - `treatment_node`
    - `treatment_value`
    - `outcome_node`
  - upstream mapping:
    - `POST {base}/v1/intervene`
    - adapter forces `model="linear"` and `horizon_steps=24`
  - result fields:
    - `outcome_node`
    - `effect`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`
  - notes:
    - this is the intentionally smaller core intervention surface
    - raw `node_summaries`, `total_events`, and `limitations` are not exposed directly
    - if the requested `outcome_node` is missing from sanitized upstream `node_summaries`, the server returns `path_not_found`

- `graph.neighbors`
  - params:
    - `node_id`
    - `scope`
    - `max_neighbors` default `10`
  - upstream mapping:
    - `POST {base}/v1/explain`
    - adapter sets `scope` to `parents` or `children`
  - result fields:
    - `node_id`
    - `scope`
    - `neighbors`
    - `total_candidate_count`
    - `truncated`
    - `edge_semantics`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`

- `graph.markov_blanket`
  - params:
    - `node_id`
    - `max_neighbors` default `10`
  - upstream mapping:
    - `POST {base}/v1/explain`
    - adapter sets `scope="markov_blanket"`
  - result fields:
    - `node_id`
    - `neighbors`
    - `total_candidate_count`
    - `truncated`
    - `edge_semantics="markov_blanket_membership"`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`

- `graph.paths`
  - params:
    - `source_node_id`
    - `target_node_id`
    - `max_paths` default `3`
  - upstream mapping:
    - `GET {base}/v1/schema/paths?from=...&to=...`
  - result fields:
    - `source_node_id`
    - `target_node_id`
    - `connected`
    - `path_count`
    - `paths`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`
  - notes:
    - path edges include Abel-specific `tau` and `tau_duration` fields when available
    - the Capability Card advertises `graph.paths` support for an additional `include_edge_signs` extension parameter namespace, but the current local adapter does not branch on that flag

### Convenience Verbs

- `traverse.parents`
  - params:
    - `node_id`
    - `top_k` default `10`
  - upstream mapping:
    - `POST {base}/v1/explain`
    - adapter sets `scope="parents"`
  - result fields:
    - `node_id`
    - `direction="parents"`
    - `nodes`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`

- `traverse.children`
  - params:
    - `node_id`
    - `top_k` default `10`
  - upstream mapping:
    - `POST {base}/v1/explain`
    - adapter sets `scope="children"`
  - result fields:
    - `node_id`
    - `direction="children"`
    - `nodes`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`

### Abel Extension Verbs

- `extensions.abel.validate_connectivity`
  - params:
    - `variables`
  - constraints:
    - minimum 2 variables
    - maximum 12 variables
  - upstream mapping:
    - `POST {base}/v1/validate`
    - adapter forces `validation_mode="iv_gate"`
  - result fields:
    - `validation_method`
    - `proxy_only`
    - `connectivity_semantics`
    - `passed`
    - `valid_variables`
    - `invalid_variables`
    - `pair_results`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`
  - notes:
    - this is a connectivity proxy, not strict d-separation or IV identification

- `extensions.abel.markov_blanket`
  - params:
    - `target_node`
  - upstream mapping:
    - `POST {base}/v1/explain`
    - adapter uses `scope="markov_blanket"`
  - result fields:
    - `target_node`
    - `drivers`
    - `markov_blanket`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`
  - notes:
    - this is an Abel convenience surface over the same primitive explain call as core `graph.markov_blanket`

- `extensions.abel.counterfactual_preview`
  - params:
    - `intervene_node`
    - `intervene_time`
    - `observe_node`
    - `observe_time`
    - `intervene_new_value`
  - upstream mapping:
    - `POST {base}/v1/counterfactual`
    - adapter forces `model="linear"`
  - result fields:
    - `intervene_node`
    - `observe_node`
    - `intervene`
    - `observe`
    - `preview_only`
    - `counterfactual_semantics`
    - `effect_support`
    - `reachable`
    - `path_count`
    - `reasoning_mode`
    - `identification_status`
    - `assumptions`
  - notes:
    - this surface is explicitly preview-only
    - it does not claim full abduction-action-prediction semantics

- `extensions.abel.intervene_time_lag`
  - params:
    - `treatment_node`
    - `treatment_value`
    - `outcome_node`
    - `horizon_steps`
    - `model` default `linear`
  - constraints:
    - `horizon_steps` must be between `1` and `168`
    - only `model="linear"` is accepted
  - upstream mapping:
    - `POST {base}/v1/intervene`
  - result fields:
    - `treatment_node`
    - `treatment_value`
    - `model`
    - `delta_unit`
    - `horizon_steps`
    - `outcome_node`
    - `reasoning_mode`
    - `outcome_summary`
    - `total_events`
    - `identification_status`
    - `assumptions`
  - notes:
    - this keeps the richer temporal propagation summary that the core `intervene.do` surface intentionally hides

## Header Behavior

Important request header behavior:

- if the caller sends `Authorization`, that value is forwarded to the upstream gateway as a Bearer token
- otherwise the server falls back to `CAP_GATEWAY_API_KEY`
- `X-Request-ID` is generated if missing and echoed on the HTTP response

## Graph Compatibility

If the request includes `context.graph_ref`, only the following values are currently accepted:

- `graph_id="abel-main"`
- `graph_version="CausalNodeV2"`

Unsupported graph references return a CAP `invalid_request` error.

## Error Behavior

The adapter layer translates upstream failures into CAP-friendly errors:

- timeout -> `computation_timeout` with HTTP 504
- upstream 404 -> `node_not_found` or `path_not_found`
- upstream 400 or 422 -> `invalid_request` or `invalid_intervention`
- upstream 503 or transport failures -> `service_unavailable`
- unexpected failures -> `upstream_error`

## Example Requests

### `meta.capabilities`

```bash
curl -s -X POST http://127.0.0.1:8000/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "verb": "meta.capabilities"
  }' | jq
```

### `graph.paths`

```bash
curl -s -X POST http://127.0.0.1:8000/cap \
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

### `extensions.abel.counterfactual_preview`

```bash
curl -s -X POST http://127.0.0.1:8000/cap \
  -H 'Content-Type: application/json' \
  -d '{
    "cap_version": "0.2.2",
    "request_id": "req-counterfactual-1",
    "verb": "extensions.abel.counterfactual_preview",
    "params": {
      "intervene_node": "NVDA_close",
      "intervene_time": "2026-03-18T00:00:00Z",
      "observe_node": "AMD_close",
      "observe_time": "2026-03-19T00:00:00Z",
      "intervene_new_value": 0.05
    }
  }' | jq
```
