import asyncio
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from abel_cap_server.cap.adapters.graph import graph_neighbors, graph_paths
from abel_cap_server.clients.abel_gateway_client import AbelGatewayClient
from abel_cap_server.core.config import Settings
from cap.core import (
    ALGORITHM_PCMCI,
    ASSUMPTION_CAUSAL_SUFFICIENCY,
    ASSUMPTION_FAITHFULNESS,
    ASSUMPTION_NO_INSTANTANEOUS_EFFECTS,
    CAPGraphRef,
    IDENTIFICATION_STATUS_NOT_APPLICABLE,
    IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
    REASONING_MODE_GRAPH_PROPAGATION,
    REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
    REASONING_MODE_OBSERVATIONAL_PREDICTION,
    REASONING_MODE_STRUCTURAL_SEMANTICS,
    REASONING_MODE_VALIDATION_GATE,
)
from cap.core.constants import CAP_VERSION
from cap.server import CAPHandlerSuccessSpec, CAPProvenanceContext, CAPProvenanceHint


def test_well_known_capability_card_is_exposed(client: TestClient) -> None:
    response = client.get("/.well-known/cap.json")

    assert response.status_code == 200
    payload = response.json()
    assert (
        payload["$schema"] == "https://causalagentprotocol.org/schema/capability-card/v0.2.2.json"
    )
    assert payload["cap_spec_version"] == CAP_VERSION
    assert payload["endpoint"] == "http://testserver/cap"
    assert payload["authentication"] == {
        "type": "none",
        "details": {},
    }
    assert payload["supported_verbs"]["core"] == [
        "meta.capabilities",
        "observe.predict",
        "intervene.do",
        "graph.neighbors",
        "graph.markov_blanket",
        "graph.paths",
    ]
    assert payload["supported_verbs"]["convenience"] == [
        "traverse.parents",
        "traverse.children",
    ]
    assert payload["assumptions"] == [
        ASSUMPTION_CAUSAL_SUFFICIENCY,
        ASSUMPTION_FAITHFULNESS,
        ASSUMPTION_NO_INSTANTANEOUS_EFFECTS,
    ]
    assert payload["causal_engine"]["family"] == "abel_primitive_adapter"
    assert payload["causal_engine"]["algorithm"] == "abel_graph_primitives"
    assert payload["causal_engine"]["supports_time_lag"] is True
    assert payload["causal_engine"]["supports_instantaneous"] is False
    assert payload["causal_engine"]["structural_mechanisms"] == {
        "available": True,
        "families": ["linear_scm"],
        "mechanism_override_supported": False,
        "counterfactual_ready": False,
    }
    assert payload["detailed_capabilities"] == {
        "graph_discovery": False,
        "graph_traversal": True,
        "temporal_multi_lag": True,
        "effect_estimation": True,
        "intervention_simulation": True,
        "counterfactual_scm": False,
        "latent_confounding_modeled": False,
        "partial_identification": False,
        "uncertainty_quantified": False,
    }
    assert payload["reasoning_modes_supported"] == [
        REASONING_MODE_OBSERVATIONAL_PREDICTION,
        REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
        REASONING_MODE_GRAPH_PROPAGATION,
        REASONING_MODE_STRUCTURAL_SEMANTICS,
        REASONING_MODE_VALIDATION_GATE,
    ]
    assert payload["graph"]["node_count"] == 11315
    assert payload["graph"]["edge_count"] == 42105965
    assert payload["disclosure_policy"]["hidden_fields"] == [
        "weight",
        "tau",
        "conditioning_set",
        "p_value",
        "confidence_interval",
        "ci_lower",
        "ci_upper",
    ]
    assert (
        "intervene.do uses the server's default linear SCM rollout over the public time-lagged graph."
        in payload["disclosure_policy"]["notes"]
    )
    assert (
        payload["extensions"]["abel"]["schema_url"] == "https://abel.ai/cap/extensions/abel/v1.json"
    )
    assert payload["extensions"]["abel"]["verbs"] == [
        "extensions.abel.validate_connectivity",
        "extensions.abel.markov_blanket",
        "extensions.abel.counterfactual_preview",
        "extensions.abel.intervene_time_lag",
    ]
    assert (
        "validate_connectivity uses an undirected shortest-path connectivity proxy rather than strict d-separation or IV identification."
        in payload["extensions"]["abel"]["notes"]
    )
    assert payload["extensions"]["abel"]["additional_params"] == {
        "graph.paths": {"include_edge_signs": "boolean"}
    }
    assert payload["access_tiers"] == [
        {
            "tier": "public",
            "verbs": [
                "meta.capabilities",
                "observe.predict",
                "intervene.do",
                "graph.neighbors",
                "graph.markov_blanket",
                "graph.paths",
                "traverse.parents",
                "traverse.children",
                "extensions.abel.validate_connectivity",
                "extensions.abel.markov_blanket",
                "extensions.abel.counterfactual_preview",
                "extensions.abel.intervene_time_lag",
            ],
            "response_detail": "summary",
            "hidden_fields": [
                "weight",
                "tau",
                "conditioning_set",
                "p_value",
                "confidence_interval",
                "ci_lower",
                "ci_upper",
            ],
        }
    ]
    assert "bindings" not in payload


def test_meta_capabilities_matches_well_known_card(client: TestClient) -> None:
    capability_card = client.get("/.well-known/cap.json").json()

    response = client.post(
        "/cap",
        json={"cap_version": "0.2.2", "request_id": "req-1", "verb": "meta.capabilities"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cap_version"] == CAP_VERSION
    assert payload["request_id"] == "req-1"
    assert payload["verb"] == "meta.capabilities"
    assert payload["status"] == "success"
    assert payload["result"] == capability_card


def test_observe_predict_endpoint_uses_cap_service_defaults(client: TestClient) -> None:
    class _FakeCapService:
        def __init__(self) -> None:
            self.payload: dict | None = None

        async def observe_predict(self, payload, headers=None):
            self.payload = payload.model_dump(exclude_none=True)
            return {
                "cap_version": "0.2.2",
                "request_id": "req-observe",
                "verb": "observe.predict",
                "status": "success",
                "result": {
                    "target_node": "BTCUSD_volume",
                    "prediction": 0.12,
                    "drivers": ["ETHUSD_volume", "DXY_close"],
                },
                "provenance": {
                    "algorithm": "primitive.predict",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 4,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            }

    fake_service = _FakeCapService()
    cast(Any, client.app).state.cap_service = fake_service

    response = client.post(
        "/cap",
        json={
            "cap_version": "0.2.2",
            "request_id": "req-observe",
            "verb": "observe.predict",
            "params": {
                "target_node": "BTCUSD_volume",
            },
        },
    )

    assert response.status_code == 200
    assert fake_service.payload == {
        "cap_version": "0.2.2",
        "request_id": "req-observe",
        "verb": "observe.predict",
        "options": {"response_detail": "summary"},
        "params": {
            "target_node": "BTCUSD_volume",
        },
    }


def test_observe_predict_adapter_uses_server_default_predictor() -> None:
    class _FakePrimitiveClient:
        async def predict(self, payload, *, timeout_ms=None):
            assert payload == {
                "target_node": "BTCUSD_volume",
                "model": "linear",
                "feature_type": "parents",
            }
            assert timeout_ms is None
            return {
                "target_node": "BTCUSD_volume",
                "prediction": 0.12,
                "drivers": ["ETHUSD_volume", "DXY_close"],
            }

    from abel_cap_server.cap.adapters.observe import observe_predict
    from cap.core import build_observe_predict_request

    payload = build_observe_predict_request(target_node="BTCUSD_volume", request_id="req-observe")
    result = asyncio.run(observe_predict(cast(Any, _FakePrimitiveClient()), payload))

    assert result.result.model_dump(exclude_none=True) == {
        "target_node": "BTCUSD_volume",
        "prediction": 0.12,
        "drivers": ["ETHUSD_volume", "DXY_close"],
    }
    assert result.provenance_hint is not None
    assert result.provenance_hint.algorithm == "primitive.predict"


def test_observe_predict_adapter_rejects_unsupported_graph_version() -> None:
    class _FakePrimitiveClient:
        async def predict(self, payload, *, timeout_ms=None):
            raise AssertionError("predict should not be called for unsupported graph_ref")

    from abel_cap_server.cap.adapters.observe import observe_predict
    from cap.core import CAPGraphRef, build_observe_predict_request
    from cap.server import CAPAdapterError

    payload = build_observe_predict_request(
        target_node="BTCUSD_volume",
        graph_ref=CAPGraphRef(graph_version="CausalNodeV3"),
        request_id="req-observe",
    )

    with pytest.raises(CAPAdapterError) as exc_info:
        asyncio.run(observe_predict(cast(Any, _FakePrimitiveClient()), payload))

    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.details == {"supported_graph_version": "CausalNodeV2"}


def test_intervene_do_adapter_rejects_unsupported_graph_id() -> None:
    class _FakePrimitiveClient:
        async def intervene(self, payload, *, timeout_ms=None):
            raise AssertionError("intervene should not be called for unsupported graph_ref")

    from abel_cap_server.cap.adapters.intervene import intervene_do
    from cap.core import build_intervene_do_request
    from cap.server import CAPAdapterError

    payload = build_intervene_do_request(
        treatment_node="NVDA_close",
        treatment_value=0.05,
        outcome_node="AMD_close",
        graph_ref=CAPGraphRef(graph_id="abel-alt"),
        request_id="req-intervene",
    )

    with pytest.raises(CAPAdapterError) as exc_info:
        asyncio.run(intervene_do(cast(Any, _FakePrimitiveClient()), payload))

    assert exc_info.value.code == "invalid_request"
    assert exc_info.value.details == {"supported_graph_id": "abel-main"}


def test_graph_paths_endpoint_uses_cap_service(client: TestClient) -> None:
    class _FakeCapService:
        def __init__(self) -> None:
            self.payload: dict | None = None

        async def graph_paths(self, payload, headers=None):
            self.payload = payload.model_dump(exclude_none=True)
            return {
                "cap_version": "0.2.2",
                "request_id": "req-paths",
                "verb": "graph.paths",
                "status": "success",
                "result": {
                    "source_node_id": "NVDA_close",
                    "target_node_id": "SONY_close",
                    "connected": True,
                    "path_count": 1,
                    "paths": [
                        {
                            "distance": 2,
                            "nodes": [
                                {
                                    "node_id": "NVDA_close",
                                    "node_name": "NVIDIA Corporation close price",
                                    "node_type": "close_price",
                                    "domain": "equities",
                                },
                                {
                                    "node_id": "AAPL_close",
                                    "node_name": "Apple Inc. close price",
                                    "node_type": "close_price",
                                    "domain": "equities",
                                },
                                {
                                    "node_id": "SONY_close",
                                    "node_name": "Sony Group Corporation close price",
                                    "node_type": "close_price",
                                    "domain": "equities",
                                },
                            ],
                            "edges": [
                                {
                                    "from_node_id": "NVDA_close",
                                    "to_node_id": "AAPL_close",
                                    "edge_type": "causes",
                                    "tau": 2,
                                    "tau_duration": "PT2H",
                                },
                                {
                                    "from_node_id": "AAPL_close",
                                    "to_node_id": "SONY_close",
                                    "edge_type": "causes",
                                    "tau": 1,
                                    "tau_duration": "PT1H",
                                },
                            ],
                        }
                    ],
                    "reasoning_mode": REASONING_MODE_STRUCTURAL_SEMANTICS,
                    "identification_status": IDENTIFICATION_STATUS_NOT_APPLICABLE,
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                "provenance": {
                    "algorithm": ALGORITHM_PCMCI,
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 5,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            }

    fake_service = _FakeCapService()
    cast(Any, client.app).state.cap_service = fake_service

    response = client.post(
        "/cap",
        json={
            "cap_version": "0.2.2",
            "request_id": "req-paths",
            "verb": "graph.paths",
            "params": {
                "source_node_id": "NVDA_close",
                "target_node_id": "SONY_close",
                "max_paths": 2,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["verb"] == "graph.paths"
    assert payload["result"]["path_count"] == 1
    assert fake_service.payload == {
        "cap_version": "0.2.2",
        "request_id": "req-paths",
        "verb": "graph.paths",
        "options": {"response_detail": "summary"},
        "params": {
            "source_node_id": "NVDA_close",
            "target_node_id": "SONY_close",
            "max_paths": 2,
        },
    }


def test_intervene_do_adapter_uses_graph_propagation_and_pcmci() -> None:
    class _FakePrimitiveClient:
        async def intervene(self, payload, *, timeout_ms=None):
            assert payload == {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "outcome_node": "AMD_close",
                "model": "linear",
                "horizon_steps": 24,
            }
            assert timeout_ms is None
            return {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "delta_unit": "delta",
                "outcome_node": "AMD_close",
                "node_summaries": [
                    {
                        "node_id": "AMD_close",
                        "final_cumulative_effect": 0.12,
                        "first_arrive_step": 1,
                        "last_arrive_step": 2,
                        "event_count": 3,
                    }
                ],
                "total_events": 3,
                "limitations": [],
            }

    from abel_cap_server.cap.adapters.intervene import intervene_do
    from cap.core import build_intervene_do_request

    payload = build_intervene_do_request(
        treatment_node="NVDA_close",
        treatment_value=0.05,
        outcome_node="AMD_close",
        request_id="req-intervene",
    )
    result = asyncio.run(intervene_do(cast(Any, _FakePrimitiveClient()), payload))

    assert result.result.reasoning_mode == REASONING_MODE_GRAPH_PROPAGATION
    assert result.result.identification_status == IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED
    assert "abel_graph_propagation_approximation" in result.result.assumptions
    assert result.result.effect == 0.12
    assert "outcome_summary" not in result.result.model_dump(exclude_none=True)
    assert "node_summaries" not in result.result.model_dump(exclude_none=True)
    assert "total_events" not in result.result.model_dump(exclude_none=True)
    assert "limitations" not in result.result.model_dump(exclude_none=True)
    assert result.provenance_hint.algorithm == ALGORITHM_PCMCI
    assert result.provenance_hint.mechanism_family_used == "linear_scm"


def test_intervene_do_adapter_accepts_non_temporal_payloads() -> None:
    class _FakePrimitiveClient:
        async def intervene(self, payload, *, timeout_ms=None):
            assert payload["horizon_steps"] == 24
            assert timeout_ms is None
            return {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "model": "linear",
                "node_summaries": [
                    {
                        "node_id": "AMD_close",
                        "final_cumulative_effect": 0.12,
                    }
                ],
                "limitations": [],
            }

    from abel_cap_server.cap.adapters.intervene import intervene_do
    from cap.core import build_intervene_do_request

    payload = build_intervene_do_request(
        treatment_node="NVDA_close",
        treatment_value=0.05,
        outcome_node="AMD_close",
        request_id="req-intervene-static",
    )
    result = asyncio.run(intervene_do(cast(Any, _FakePrimitiveClient()), payload))

    assert result.result.reasoning_mode == REASONING_MODE_GRAPH_PROPAGATION
    assert result.result.effect == 0.12
    assert "outcome_summary" not in result.result.model_dump(exclude_none=True)
    assert "total_events" not in result.result.model_dump(exclude_none=True)


def test_intervene_do_adapter_prefers_requested_outcome_over_mismatched_top_level_summary() -> None:
    class _FakePrimitiveClient:
        async def intervene(self, payload, *, timeout_ms=None):
            assert timeout_ms is None
            return {
                "outcome_summary": {
                    "node_id": "OTHER_close",
                    "final_cumulative_effect": 999.0,
                },
                "node_summaries": [
                    {
                        "node_id": "AMD_close",
                        "final_cumulative_effect": 0.12,
                    }
                ],
            }

    from abel_cap_server.cap.adapters.intervene import intervene_do
    from cap.core import build_intervene_do_request

    payload = build_intervene_do_request(
        treatment_node="NVDA_close",
        treatment_value=0.05,
        outcome_node="AMD_close",
        request_id="req-intervene-mismatch",
    )
    result = asyncio.run(intervene_do(cast(Any, _FakePrimitiveClient()), payload))

    assert result.result.effect == 0.12


def test_intervene_do_adapter_requires_matching_node_summary() -> None:
    class _FakePrimitiveClient:
        async def intervene(self, payload, *, timeout_ms=None):
            assert timeout_ms is None
            return {
                "outcome_summary": {
                    "node_id": "AMD_close",
                    "final_cumulative_effect": 0.12,
                },
                "node_summaries": [],
            }

    from abel_cap_server.cap.adapters.intervene import intervene_do
    from cap.core import build_intervene_do_request
    from cap.server import CAPAdapterError

    payload = build_intervene_do_request(
        treatment_node="NVDA_close",
        treatment_value=0.05,
        outcome_node="AMD_close",
        request_id="req-intervene-missing-summary",
    )

    with pytest.raises(CAPAdapterError) as exc_info:
        asyncio.run(intervene_do(cast(Any, _FakePrimitiveClient()), payload))

    assert exc_info.value.code == "path_not_found"


def test_validate_connectivity_adapter_uses_proxy_gate_semantics() -> None:
    class _FakePrimitiveClient:
        async def validate(self, payload, *, timeout_ms=None):
            assert payload == {
                "variables": ["NVDA_close", "AAPL_close", "DXY_close"],
                "validation_mode": "iv_gate",
            }
            assert timeout_ms is None
            return {
                "validation_method": "shortest_path_connectivity_proxy",
                "passed": False,
                "valid_variables": ["NVDA_close", "AAPL_close"],
                "invalid_variables": [
                    {
                        "node": "DXY_close",
                        "reason": "No undirected shortest path found to at least one peer variable within max_depth=10.",
                    }
                ],
                "pair_results": [
                    {"node_a": "NVDA_close", "node_b": "AAPL_close", "connected": True},
                    {"node_a": "NVDA_close", "node_b": "DXY_close", "connected": False},
                ],
                "limitations": [],
            }

    from abel_cap_server.cap.adapters.extensions import validate_connectivity
    from abel_cap_server.cap.contracts import ExtensionsValidateConnectivityRequest

    payload = ExtensionsValidateConnectivityRequest.model_validate(
        {
            "cap_version": "0.2.2",
            "request_id": "req-validate",
            "verb": "extensions.abel.validate_connectivity",
            "params": {"variables": ["NVDA_close", "AAPL_close", "DXY_close"]},
        }
    )
    result = asyncio.run(validate_connectivity(cast(Any, _FakePrimitiveClient()), payload))

    assert result.result.validation_method == "shortest_path_connectivity_proxy"
    assert result.result.proxy_only is True
    assert result.result.connectivity_semantics == "undirected_shortest_path_proxy"
    assert result.result.passed is False
    assert result.result.valid_variables == ["NVDA_close", "AAPL_close"]
    assert result.result.invalid_variables[0].node == "DXY_close"
    assert result.result.pair_results[1].connected is False
    assert result.result.reasoning_mode == REASONING_MODE_VALIDATION_GATE
    assert result.result.identification_status == IDENTIFICATION_STATUS_NOT_APPLICABLE
    assert "abel_connectivity_proxy_not_strict_d_separation" in result.result.assumptions
    assert result.provenance_hint.algorithm == "primitive.validate"


def test_counterfactual_preview_adapter_uses_graph_propagation_and_pcmci() -> None:
    class _FakePrimitiveClient:
        async def counterfactual(self, payload, *, timeout_ms=None):
            assert payload["intervene_node"] == "NVDA_close"
            assert payload["observe_node"] == "AMD_close"
            assert payload["model"] == "linear"
            assert timeout_ms is None
            return {
                "intervene_node": "NVDA_close",
                "observe_node": "AMD_close",
                "intervene": {"value": 0.05},
                "observe": {"original_value": 0.1, "new_value": 0.12, "change": 0.02},
                "meta": {"reachable": True, "path_count": 1},
                "limitations": [],
            }

    from abel_cap_server.cap.adapters.extensions import counterfactual_preview
    from abel_cap_server.cap.contracts import ExtensionsCounterfactualPreviewRequest

    payload = ExtensionsCounterfactualPreviewRequest.model_validate(
        {
            "cap_version": "0.2.2",
            "request_id": "req-counterfactual",
            "verb": "extensions.abel.counterfactual_preview",
            "params": {
                "intervene_node": "NVDA_close",
                "intervene_time": "2026-03-18T00:00:00Z",
                "observe_node": "AMD_close",
                "observe_time": "2026-03-19T00:00:00Z",
                "intervene_new_value": 0.05,
            },
        }
    )
    result = asyncio.run(counterfactual_preview(cast(Any, _FakePrimitiveClient()), payload))

    assert result.result.reasoning_mode == REASONING_MODE_GRAPH_PROPAGATION
    assert result.result.identification_status == IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED
    assert "abel_graph_propagation_approximation" in result.result.assumptions
    assert (
        "abel_counterfactual_preview_not_abduction_action_prediction" in result.result.assumptions
    )
    assert result.result.preview_only is True
    assert result.result.counterfactual_semantics == "approximate_graph_propagation"
    assert result.result.effect_support == "reachable"
    assert result.result.observe.factual_value == 0.1
    assert result.result.observe.counterfactual_value == 0.12
    assert result.result.observe.change == 0.02
    assert "reasoning_mode" not in result.result.observe.model_dump(exclude_none=True)
    assert "limitations" not in result.result.model_dump(exclude_none=True)
    assert result.provenance_hint.algorithm == ALGORITHM_PCMCI
    assert result.provenance_hint.mechanism_family_used == "linear_scm"


def test_intervene_time_lag_extension_preserves_richer_temporal_payload() -> None:
    class _FakePrimitiveClient:
        async def intervene(self, payload, *, timeout_ms=None):
            assert payload["horizon_steps"] == 24
            assert timeout_ms is None
            return {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "model": "linear",
                "delta_unit": "delta",
                "horizon_steps": 24,
                "node_summaries": [
                    {
                        "node_id": "AMD_close",
                        "final_cumulative_effect": 0.12,
                        "first_arrive_step": 1,
                        "last_arrive_step": 2,
                        "event_count": 3,
                    }
                ],
                "total_events": 3,
            }

    from abel_cap_server.cap.adapters.extensions import intervene_time_lag
    from abel_cap_server.cap.contracts import ExtensionsInterveneTimeLagRequest

    payload = ExtensionsInterveneTimeLagRequest.model_validate(
        {
            "cap_version": "0.2.2",
            "request_id": "req-time-lag",
            "verb": "extensions.abel.intervene_time_lag",
            "params": {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "outcome_node": "AMD_close",
                "horizon_steps": 24,
                "model": "linear",
            },
        }
    )
    result = asyncio.run(intervene_time_lag(cast(Any, _FakePrimitiveClient()), payload))

    assert result.result.delta_unit == "delta"
    assert result.result.horizon_steps == 24
    assert result.result.total_events == 3
    assert result.result.reasoning_mode == REASONING_MODE_GRAPH_PROPAGATION
    assert result.result.outcome_summary is not None
    assert result.result.outcome_summary.first_arrive_step == 1
    assert result.result.outcome_summary.last_arrive_step == 2
    assert result.result.outcome_summary.event_count == 3
    assert "node_summaries" not in result.result.model_dump(exclude_none=True)
    assert result.provenance_hint.algorithm == ALGORITHM_PCMCI


def test_cap_dispatch_auto_reduces_success_spec_from_cap_service(client: TestClient) -> None:
    class _FakeCapService:
        def __init__(self) -> None:
            self.payload: dict | None = None

        def build_provenance_context(self) -> CAPProvenanceContext:
            return CAPProvenanceContext(
                graph_version="CausalNodeV2",
                server_name="abel-cap",
                server_version="0.1.0",
            )

        async def graph_paths(self, payload, headers=None):
            self.payload = payload.model_dump(exclude_none=True)
            return CAPHandlerSuccessSpec(
                result={
                    "source_node_id": payload.params.source_node_id,
                    "target_node_id": payload.params.target_node_id,
                    "connected": True,
                    "path_count": 0,
                    "paths": [],
                    "reasoning_mode": REASONING_MODE_STRUCTURAL_SEMANTICS,
                    "identification_status": IDENTIFICATION_STATUS_NOT_APPLICABLE,
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                provenance_hint=CAPProvenanceHint(algorithm=ALGORITHM_PCMCI),
            )

    fake_service = _FakeCapService()
    cast(Any, client.app).state.cap_service = fake_service

    response = client.post(
        "/cap",
        json={
            "cap_version": "0.2.2",
            "request_id": "req-auto-reduce",
            "verb": "graph.paths",
            "params": {
                "source_node_id": "NVDA_close",
                "target_node_id": "SONY_close",
                "max_paths": 2,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["verb"] == "graph.paths"
    assert payload["result"]["connected"] is True
    assert "limitations" not in payload["result"]
    assert payload["provenance"]["algorithm"] == ALGORITHM_PCMCI
    assert payload["provenance"]["graph_version"] == "CausalNodeV2"
    assert payload["provenance"]["server_name"] == "abel-cap"
    assert payload["provenance"]["computation_time_ms"] >= 1


def test_cap_dispatch_returns_verb_not_supported_for_unknown_verb(client: TestClient) -> None:
    response = client.post(
        "/cap",
        json={
            "cap_version": "0.2.2",
            "request_id": "req-unsupported",
            "verb": "graph.unknown",
            "params": {},
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "verb_not_supported"


def test_legacy_cap_route_is_not_mounted(client: TestClient) -> None:
    response = client.post("/observe/predict", json={})
    assert response.status_code == 404


def test_legacy_meta_route_is_not_mounted(client: TestClient) -> None:
    response = client.post("/meta/capabilities", json={})
    assert response.status_code == 404


def test_graph_neighbors_adapter_maps_primitive_explain() -> None:
    class _FakePrimitiveClient:
        def __init__(self) -> None:
            self.scopes: list[str] = []

        async def explain(self, payload, *, timeout_ms=None):
            self.scopes.append(payload["scope"])
            if payload["scope"] == "markov_blanket":
                return {
                    "target_node": payload["target_node"],
                    "parents": ["AAPL_close"],
                    "children": ["SONY_close"],
                    "spouses": ["MSFT_close"],
                    "limitations": [
                        "Explanation output hides graph internals and only returns node identities."
                    ],
                    "weight": 0.9,
                    "tau": 2,
                }
            return {
                "target_node": payload["target_node"],
                "related_nodes": ["SONY_close"],
                "limitations": [
                    "Explanation output hides graph internals and only returns node identities."
                ],
            }

    primitive_client = _FakePrimitiveClient()
    payload = {
        "cap_version": "0.2.2",
        "request_id": "req-neighbors",
        "verb": "graph.neighbors",
        "params": {
            "node_id": "NVDA_close",
            "scope": "children",
            "max_neighbors": 10,
        },
    }
    result = asyncio.run(
        graph_neighbors(
            cast(Any, primitive_client),
            service_neighbors_request(payload),
        )
    )

    assert primitive_client.scopes == ["children"]
    assert [item.model_dump() for item in result.result.neighbors] == [
        {"node_id": "SONY_close", "roles": ["child"]},
    ]
    assert result.result.scope == "children"
    assert result.result.total_candidate_count == 1
    assert result.result.truncated is False
    assert result.result.edge_semantics == "identified_causal_effect"
    assert result.result.reasoning_mode == "identified_causal_effect"
    assert result.result.identification_status == "identified"
    assert result.provenance_hint.algorithm == "primitive.explain"
    assert "weight" not in str(result.result.model_dump())
    assert "tau" not in str(result.result.model_dump())


def test_graph_markov_blanket_adapter_maps_explain_roles() -> None:
    class _FakePrimitiveClient:
        def __init__(self) -> None:
            self.scopes: list[str] = []

        async def explain(self, payload, *, timeout_ms=None):
            self.scopes.append(payload["scope"])
            return {
                "target_node": payload["target_node"],
                "parents": ["AAPL_close"],
                "children": ["SONY_close"],
                "spouses": ["MSFT_close"],
                "limitations": [
                    "Explanation output hides graph internals and only returns node identities."
                ],
                "weight": 0.9,
                "tau": 2,
            }

    from abel_cap_server.cap.adapters.graph import graph_markov_blanket
    from cap.core import GraphMarkovBlanketRequest

    primitive_client = _FakePrimitiveClient()
    payload = GraphMarkovBlanketRequest.model_validate(
        {
            "cap_version": "0.2.2",
            "request_id": "req-mb",
            "verb": "graph.markov_blanket",
            "params": {"node_id": "NVDA_close", "max_neighbors": 10},
        }
    )

    result = asyncio.run(graph_markov_blanket(cast(Any, primitive_client), payload))

    assert primitive_client.scopes == ["markov_blanket"]
    assert [item.model_dump() for item in result.result.neighbors] == [
        {"node_id": "AAPL_close", "roles": ["parent"]},
        {"node_id": "MSFT_close", "roles": ["spouse"]},
        {"node_id": "SONY_close", "roles": ["child"]},
    ]
    assert result.result.total_candidate_count == 3
    assert result.result.edge_semantics == "markov_blanket_membership"
    assert result.result.reasoning_mode == REASONING_MODE_STRUCTURAL_SEMANTICS
    assert result.result.identification_status == IDENTIFICATION_STATUS_NOT_APPLICABLE


def test_traverse_parents_adapter_uses_verb_specific_top_k() -> None:
    class _FakePrimitiveClient:
        def __init__(self) -> None:
            self.scopes: list[str] = []

        async def explain(self, payload, *, timeout_ms=None):
            self.scopes.append(payload["scope"])
            return {
                "target_node": payload["target_node"],
                "related_nodes": ["AAPL_close", "MSFT_close", "QQQ_close"],
            }

    from abel_cap_server.cap.adapters.graph import traverse_parents
    from cap.core import TraverseParentsRequest

    primitive_client = _FakePrimitiveClient()
    payload = TraverseParentsRequest.model_validate(
        {
            "cap_version": "0.2.2",
            "request_id": "req-traverse-parents",
            "verb": "traverse.parents",
            "params": {"node_id": "NVDA_close", "top_k": 2},
        }
    )

    result = asyncio.run(traverse_parents(cast(Any, primitive_client), payload))

    assert primitive_client.scopes == ["parents"]
    assert result.result.direction == "parents"
    assert result.result.nodes == ["AAPL_close", "MSFT_close"]
    assert result.result.reasoning_mode == REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT
    assert result.result.identification_status == "identified"


def test_traverse_children_adapter_uses_verb_specific_top_k() -> None:
    class _FakePrimitiveClient:
        def __init__(self) -> None:
            self.scopes: list[str] = []

        async def explain(self, payload, *, timeout_ms=None):
            self.scopes.append(payload["scope"])
            return {
                "target_node": payload["target_node"],
                "related_nodes": ["AMD_close", "SONY_close"],
            }

    from abel_cap_server.cap.adapters.graph import traverse_children
    from cap.core import TraverseChildrenRequest

    primitive_client = _FakePrimitiveClient()
    payload = TraverseChildrenRequest.model_validate(
        {
            "cap_version": "0.2.2",
            "request_id": "req-traverse-children",
            "verb": "traverse.children",
            "params": {"node_id": "NVDA_close", "top_k": 1},
        }
    )

    result = asyncio.run(traverse_children(cast(Any, primitive_client), payload))

    assert primitive_client.scopes == ["children"]
    assert result.result.direction == "children"
    assert result.result.nodes == ["AMD_close"]
    assert result.result.reasoning_mode == REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT
    assert result.result.identification_status == "identified"


def test_graph_paths_adapter_maps_schema_paths() -> None:
    class _FakePrimitiveClient:
        async def fetch_schema_paths(
            self,
            *,
            source_node_id: str,
            target_node_id: str,
            timeout_ms=None,
        ):
            assert source_node_id == "NVDA_close"
            assert target_node_id == "SONY_close"
            assert timeout_ms is None
            return {
                "method": ALGORITHM_PCMCI,
                "connected": True,
                "paths": [
                    {
                        "distance": 2,
                        "nodes": [
                            {
                                "node_id": "NVDA_close",
                                "display_name": "NVIDIA Corporation close price",
                                "domain": "equities",
                                "metric_type": "close_price",
                            },
                            {
                                "node_id": "AAPL_close",
                                "display_name": "Apple Inc. close price",
                                "domain": "equities",
                                "metric_type": "close_price",
                            },
                            {
                                "node_id": "SONY_close",
                                "display_name": "Sony Group Corporation close price",
                                "domain": "equities",
                                "metric_type": "close_price",
                            },
                        ],
                        "edges": [
                            {
                                "from_node_id": "NVDA_close",
                                "to_node_id": "AAPL_close",
                                "edge_type": "causes",
                                "tau": 2,
                            },
                            {
                                "from_node_id": "AAPL_close",
                                "to_node_id": "SONY_close",
                                "edge_type": "causes",
                                "tau": 1,
                            },
                        ],
                    }
                ],
            }

    primitive_client = cast(Any, _FakePrimitiveClient())

    payload = {
        "cap_version": "0.2.2",
        "request_id": "req-paths",
        "verb": "graph.paths",
        "params": {
            "source_node_id": "NVDA_close",
            "target_node_id": "SONY_close",
            "max_paths": 2,
        },
    }
    result = asyncio.run(graph_paths(primitive_client, service_paths_request(payload)))

    assert result.result.connected is True
    assert result.result.path_count == 1
    assert "limitations" not in result.result.model_dump(exclude_none=True)
    assert result.provenance_hint.algorithm == ALGORITHM_PCMCI
    assert [item.model_dump() for item in result.result.paths] == [
        {
            "distance": 2,
            "nodes": [
                {
                    "node_id": "NVDA_close",
                    "node_name": "NVIDIA Corporation close price",
                    "node_type": "close_price",
                    "domain": "equities",
                },
                {
                    "node_id": "AAPL_close",
                    "node_name": "Apple Inc. close price",
                    "node_type": "close_price",
                    "domain": "equities",
                },
                {
                    "node_id": "SONY_close",
                    "node_name": "Sony Group Corporation close price",
                    "node_type": "close_price",
                    "domain": "equities",
                },
            ],
            "edges": [
                {
                    "from_node_id": "NVDA_close",
                    "to_node_id": "AAPL_close",
                    "edge_type": "causes",
                    "tau": 2,
                    "tau_duration": "PT2H",
                },
                {
                    "from_node_id": "AAPL_close",
                    "to_node_id": "SONY_close",
                    "edge_type": "causes",
                    "tau": 1,
                    "tau_duration": "PT1H",
                },
            ],
        }
    ]


def test_cap_server_forwards_request_authorization_to_gateway(client: TestClient) -> None:
    from abel_cap_server.cap.service import CapService

    captured: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        return httpx.Response(
            200,
            json={"prediction": 0.12, "intercept": 0.01, "drivers": ["ETHUSD_volume"]},
        )

    transport = httpx.MockTransport(_handler)
    settings = Settings(
        app_env="test",
        log_json=False,
        cap_upstream_base_url="https://cap-sit.abel.ai/api",
        gateway_api_key=SecretStr("fallback-gateway-key"),
    )
    primitive_client = AbelGatewayClient(settings=settings, transport=transport)
    cast(Any, client.app).state.cap_service = CapService(
        settings=settings,
        primitive_client=primitive_client,
    )

    response = client.post(
        "/cap",
        headers={"Authorization": "Bearer caller-key"},
        json={
            "cap_version": "0.2.2",
            "request_id": "req-observe-auth",
            "verb": "observe.predict",
            "params": {
                "target_node": "BTCUSD_volume",
            },
        },
    )

    assert response.status_code == 200
    assert captured["path"] == "https://cap-sit.abel.ai/api/v1/predict"
    assert captured["authorization"] == "Bearer caller-key"

    asyncio.run(primitive_client.aclose())


def test_abel_gateway_client_uses_cap_sit_api_base_url_and_bearer_authorization() -> None:
    captured: dict[str, str] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        return httpx.Response(200, json={"prediction": 0.12, "intercept": 0.01, "drivers": []})

    transport = httpx.MockTransport(_handler)
    client = AbelGatewayClient(
        settings=Settings(
            app_env="test",
            log_json=False,
            cap_upstream_base_url="https://cap-sit.abel.ai/api",
            gateway_api_key=SecretStr("demo-app-key"),
        ),
        transport=transport,
    )

    result = asyncio.run(
        client.predict(
            {"target_node": "NVDA_close", "model": "linear", "feature_type": "parents"},
        )
    )

    assert captured["path"] == "https://cap-sit.abel.ai/api/v1/predict"
    assert captured["authorization"] == "Bearer demo-app-key"
    assert result["prediction"] == 0.12

def service_neighbors_request(payload: dict):
    from abel_cap_server.cap.contracts import GraphNeighborsRequest

    return GraphNeighborsRequest.model_validate(payload)


def service_paths_request(payload: dict):
    from abel_cap_server.cap.contracts import GraphPathsRequest

    return GraphPathsRequest.model_validate(payload)
