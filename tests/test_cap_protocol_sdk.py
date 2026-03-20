import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.requests import Request

from abel_cap_server.cap.catalog import (
    CapabilityCard as AppCapabilityCard,
    build_dispatch_registry,
    build_supported_verbs,
)
from abel_cap_client.client import DEFAULT_CAP_ROUTES
from abel_cap_server.cap.contracts import (
    GraphPathsRequest as AppGraphPathsRequest,
)
from abel_cap_server.cap.disclosure import sanitize_hidden_fields
from abel_cap_server.cap.provenance import CAPProvenance as AppCAPProvenance
from cap.client import AsyncCAPClient, CAPClientRoutes
from cap.core import (
    ALGORITHM_PCMCI,
    ASSUMPTION_CAUSAL_SUFFICIENCY,
    CAPHTTPError,
    CAPGraphRef,
    CANONICAL_ASSUMPTIONS,
    CANONICAL_IDENTIFICATION_STATUSES,
    CANONICAL_MECHANISM_FAMILIES,
    CANONICAL_REASONING_MODES,
    IDENTIFICATION_STATUS_NOT_APPLICABLE,
    IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
    MECHANISM_FAMILY_NONE,
    RECOMMENDED_ALGORITHM_NAMES,
    REASONING_MODE_GRAPH_PROPAGATION,
    REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
    REASONING_MODE_STRUCTURAL_SEMANTICS,
    CAPRequestOptions,
    CapabilityA2ABinding,
    CapabilityBindings,
    CapabilityCard,
    CapabilityCausalEngine,
    CapabilityDetailedCapabilities,
    CapabilityMCPBinding,
    CapabilityStructuralMechanisms,
    build_capability_access_tier,
    build_capability_disclosure_policy,
    build_extension_namespace,
    build_graph_paths_request,
    build_intervene_do_request,
    build_observe_predict_request,
    build_traverse_children_request,
    build_traverse_parents_request,
    sanitize_fields,
)
from cap.core.contracts import (
    CAPProvenance,
    GraphPathsRequest,
    InterveneDoResponse,
    ObservePredictResponse,
)
from cap.core.errors import CAPErrorBody
from cap.server import (
    CAPHandlerSuccessSpec,
    CAPProvenanceContext,
    CAPProvenanceHint,
    CAPVerbRegistry,
    GRAPH_PATHS_CONTRACT,
    build_cap_success_response,
    build_cap_provenance,
    build_fastapi_cap_dispatcher,
    build_handler_success,
    reduce_handler_success,
    register_cap_exception_handlers,
)


def test_graph_paths_builder_uses_cap_envelope_defaults() -> None:
    payload = build_graph_paths_request(
        source_node_id="NVDA_close",
        target_node_id="AMD_close",
        max_paths=2,
        request_id="req-paths",
        options=CAPRequestOptions(timeout_ms=1200, response_detail="full"),
    )

    assert payload.model_dump(exclude_none=True) == {
        "cap_version": "0.2.2",
        "request_id": "req-paths",
        "options": {"timeout_ms": 1200, "response_detail": "full"},
        "verb": "graph.paths",
        "params": {
            "source_node_id": "NVDA_close",
            "target_node_id": "AMD_close",
            "max_paths": 2,
        },
    }


def test_observe_predict_builder_can_include_graph_ref_without_model_hints() -> None:
    payload = build_observe_predict_request(
        target_node="NVDA_close",
        graph_ref=CAPGraphRef(graph_id="abel-main", graph_version="CausalNodeV2"),
        request_id="req-observe",
    )

    assert payload.model_dump(exclude_none=True) == {
        "cap_version": "0.2.2",
        "request_id": "req-observe",
        "options": {"response_detail": "summary"},
        "context": {
            "graph_ref": {
                "graph_id": "abel-main",
                "graph_version": "CausalNodeV2",
            }
        },
        "verb": "observe.predict",
        "params": {
            "target_node": "NVDA_close",
        },
    }


def test_intervene_do_builder_can_include_graph_ref() -> None:
    payload = build_intervene_do_request(
        treatment_node="NVDA_close",
        treatment_value=0.05,
        outcome_node="AMD_close",
        graph_ref=CAPGraphRef(graph_id="abel-main", graph_version="CausalNodeV2"),
        request_id="req-intervene",
    )

    assert payload.model_dump(exclude_none=True) == {
        "cap_version": "0.2.2",
        "request_id": "req-intervene",
        "options": {"response_detail": "summary"},
        "context": {
            "graph_ref": {
                "graph_id": "abel-main",
                "graph_version": "CausalNodeV2",
            }
        },
        "verb": "intervene.do",
        "params": {
            "treatment_node": "NVDA_close",
            "treatment_value": 0.05,
            "outcome_node": "AMD_close",
        },
    }


def test_intervene_do_builder_requires_outcome_node() -> None:
    with pytest.raises(TypeError):
        build_intervene_do_request(
            treatment_node="NVDA_close",
            treatment_value=0.05,
        )


def test_traverse_parents_builder_uses_verb_specific_params() -> None:
    payload = build_traverse_parents_request(
        node_id="NVDA_close",
        top_k=7,
        graph_ref=CAPGraphRef(graph_id="abel-main", graph_version="CausalNodeV2"),
        request_id="req-traverse-parents",
    )

    assert payload.model_dump(exclude_none=True) == {
        "cap_version": "0.2.2",
        "request_id": "req-traverse-parents",
        "options": {"response_detail": "summary"},
        "context": {
            "graph_ref": {
                "graph_id": "abel-main",
                "graph_version": "CausalNodeV2",
            }
        },
        "verb": "traverse.parents",
        "params": {
            "node_id": "NVDA_close",
            "top_k": 7,
        },
    }


def test_traverse_children_builder_uses_verb_specific_params() -> None:
    payload = build_traverse_children_request(
        node_id="NVDA_close",
        top_k=4,
        request_id="req-traverse-children",
    )

    assert payload.model_dump(exclude_none=True) == {
        "cap_version": "0.2.2",
        "request_id": "req-traverse-children",
        "options": {"response_detail": "summary"},
        "verb": "traverse.children",
        "params": {
            "node_id": "NVDA_close",
            "top_k": 4,
        },
    }


def test_observe_predict_response_accepts_lightweight_observational_shape() -> None:
    response = ObservePredictResponse.model_validate(
        {
            "cap_version": "0.2.2",
            "request_id": "req-observe",
            "verb": "observe.predict",
            "status": "success",
            "result": {
                "target_node": "NVDA_close",
                "prediction": 0.12,
                "drivers": ["SOXX_close"],
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
    )

    assert response.result.target_node == "NVDA_close"
    assert response.result.model_dump(exclude_none=True) == {
        "target_node": "NVDA_close",
        "prediction": 0.12,
        "drivers": ["SOXX_close"],
    }


def test_routes_map_path_aliases_back_to_verbs() -> None:
    routes = DEFAULT_CAP_ROUTES

    assert routes.resolve("graph.neighbors") == "/cap"
    assert routes.resolve("intervene.do") == "/cap"
    assert routes.resolve_verb("intervene/do") == "intervene.do"
    assert routes.resolve_verb("/extensions/abel/markov_blanket/") == (
        "extensions.abel.markov_blanket"
    )


def test_server_registry_tracks_registered_verbs() -> None:
    registry = CAPVerbRegistry()

    request_model = type(build_graph_paths_request(source_node_id="a", target_node_id="b"))

    registry.register_core_contract(
        GRAPH_PATHS_CONTRACT,
        handler=lambda payload, request: {},
    )
    verb = registry.register_extension(
        namespace="abel",
        name="counterfactual_preview",
        request_model=request_model,
        response_model=request_model,
        handler=lambda payload, request: {},
    )

    assert registry.get("graph.paths") is not None
    assert verb == "extensions.abel.counterfactual_preview"
    assert registry.supported_verbs == ["extensions.abel.counterfactual_preview", "graph.paths"]
    assert registry.verbs_for_surface("core") == ["graph.paths"]
    assert registry.verbs_for_surface("extension") == ["extensions.abel.counterfactual_preview"]
    assert registry.extension_verbs_by_namespace == {
        "abel": ["extensions.abel.counterfactual_preview"]
    }


def test_server_registry_accepts_direct_handler_registration() -> None:
    registry = CAPVerbRegistry()

    def _handler(payload, request):  # pragma: no cover - signature test only
        return {}

    registry.register_core_contract(
        GRAPH_PATHS_CONTRACT,
        handler=_handler,
    )

    spec = registry.get("graph.paths")
    assert spec is not None
    assert spec.handler is not None


def test_server_registry_supports_single_line_register_api() -> None:
    registry = CAPVerbRegistry()

    @registry.core(GRAPH_PATHS_CONTRACT)
    def _graph_paths(payload, request):  # pragma: no cover - signature test only
        return {}

    request_model = type(build_graph_paths_request(source_node_id="a", target_node_id="b"))

    @registry.core(
        "traverse.parents",
        request_model=request_model,
        response_model=request_model,
        surface="convenience",
    )
    def _traverse_parents(payload, request):  # pragma: no cover - signature test only
        return {}

    @registry.extension(
        namespace="abel",
        name="counterfactual_preview",
        request_model=request_model,
        response_model=request_model,
    )
    def _counterfactual_preview(payload, request):  # pragma: no cover - signature test only
        return {}

    assert registry.verbs_for_surface("core") == ["graph.paths"]
    assert registry.verbs_for_surface("convenience") == ["traverse.parents"]
    assert registry.extension_verbs_by_namespace == {
        "abel": ["extensions.abel.counterfactual_preview"]
    }


def test_server_registry_rejects_invalid_core_or_extension_names() -> None:
    registry = CAPVerbRegistry()
    request_model = type(build_graph_paths_request(source_node_id="a", target_node_id="b"))

    with pytest.raises(ValueError):
        registry.register_core_verb(
            "extensions.abel.bad",
            request_model=request_model,
            response_model=request_model,
            handler=lambda payload, request: {},
        )

    with pytest.raises(ValueError):
        registry.register_extension(
            namespace="abel.ai",
            name="counterfactual_preview",
            request_model=request_model,
            response_model=request_model,
            handler=lambda payload, request: {},
        )


def test_protocol_disclosure_sanitizer_removes_forbidden_fields_recursively() -> None:
    payload = {
        "weight": 0.7,
        "node_id": "NVDA_close",
        "children": [
            {
                "tau": 2,
                "node_id": "AAPL_close",
                "details": {"ci_lower": 0.1, "visible": True},
            }
        ],
    }

    assert sanitize_fields(payload, forbidden_fields={"weight", "tau", "ci_lower"}) == {
        "node_id": "NVDA_close",
        "children": [
            {
                "node_id": "AAPL_close",
                "details": {"visible": True},
            }
        ],
    }
    assert sanitize_hidden_fields(payload) == {
        "node_id": "NVDA_close",
        "children": [
            {
                "node_id": "AAPL_close",
                "details": {"visible": True},
            }
        ],
    }


def test_protocol_exception_handlers_wrap_cap_http_and_validation_errors() -> None:
    app = FastAPI()
    register_cap_exception_handlers(app)

    class _CAPPayload(BaseModel):
        cap_version: str
        request_id: str
        verb: str
        params: dict[str, str]

    @app.post("/cap/http-error")
    async def _http_error() -> None:
        raise CAPHTTPError(
            status_code=409,
            message="Conflict.",
            cap_error=CAPErrorBody(code="upstream_error", message="Conflict.", details={"a": 1}),
        )

    @app.post("/cap/validate")
    async def _validate(payload: _CAPPayload) -> dict[str, str]:
        return {"verb": payload.verb}

    client = TestClient(app)

    http_error_response = client.post(
        "/cap/http-error",
        json={"cap_version": "0.2.2", "request_id": "req-http", "verb": "graph.paths"},
    )
    assert http_error_response.status_code == 409
    assert http_error_response.json() == {
        "cap_version": "0.2.2",
        "request_id": "req-http",
        "verb": "graph.paths",
        "status": "error",
        "error": {
            "code": "upstream_error",
            "message": "Conflict.",
            "details": {"a": 1},
        },
    }

    validation_error_response = client.post(
        "/cap/validate",
        json={"cap_version": "0.2.2", "request_id": "req-validate"},
    )
    assert validation_error_response.status_code == 422
    validation_payload = validation_error_response.json()
    assert validation_payload["cap_version"] == "0.2.2"
    assert validation_payload["request_id"] == "req-validate"
    assert validation_payload["verb"] == "unknown"
    assert validation_payload["status"] == "error"
    assert validation_payload["error"]["code"] == "invalid_request"
    assert validation_payload["error"]["message"] == "CAP request validation failed."
    assert validation_payload["error"]["details"]["errors"]


def test_capability_card_builders_keep_namespace_and_disclosure_shape() -> None:
    access_tier = build_capability_access_tier(
        tier="public",
        verbs=["graph.paths"],
        hidden_fields=["tau", "weight"],
        response_detail="raw",
    )
    disclosure_policy = build_capability_disclosure_policy(
        hidden_fields=["tau", "weight"],
        notes=["summary-only"],
        default_response_detail="raw",
    )
    extension_namespace = build_extension_namespace(
        schema_url="https://abel.ai/cap/extensions/abel/v1.json",
        verbs=["extensions.abel.counterfactual_preview"],
        additional_params={"graph.paths": {"include_edge_signs": "boolean"}},
        notes=["abel-owned"],
    )

    assert access_tier.model_dump() == {
        "tier": "public",
        "verbs": ["graph.paths"],
        "response_detail": "raw",
        "hidden_fields": ["tau", "weight"],
    }
    assert disclosure_policy.model_dump() == {
        "hidden_fields": ["tau", "weight"],
        "default_response_detail": "raw",
        "notes": ["summary-only"],
    }
    assert extension_namespace.model_dump() == {
        "schema_url": "https://abel.ai/cap/extensions/abel/v1.json",
        "verbs": ["extensions.abel.counterfactual_preview"],
        "additional_params": {"graph.paths": {"include_edge_signs": "boolean"}},
        "notes": ["abel-owned"],
    }


def test_protocol_exports_canonical_names_without_closing_algorithm_space() -> None:
    assert REASONING_MODE_GRAPH_PROPAGATION in CANONICAL_REASONING_MODES
    assert IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED in CANONICAL_IDENTIFICATION_STATUSES
    assert MECHANISM_FAMILY_NONE in CANONICAL_MECHANISM_FAMILIES
    assert ASSUMPTION_CAUSAL_SUFFICIENCY in CANONICAL_ASSUMPTIONS
    assert ALGORITHM_PCMCI in RECOMMENDED_ALGORITHM_NAMES

    provenance = CAPProvenance(
        algorithm="vendor.custom.method",
        graph_version="CausalNodeV2",
        computation_time_ms=4,
        server_name="abel-cap",
        server_version="0.1.0",
        cap_spec_version="0.2.2",
    )

    assert provenance.algorithm == "vendor.custom.method"


def test_capability_card_models_support_richer_draft_fields() -> None:
    card = CapabilityCard.model_validate(
        {
            "$schema": "https://causalagentprotocol.org/schema/capability-card/v0.2.2.json",
            "name": "Example CAP",
            "description": "Example",
            "version": "0.1.0",
            "cap_spec_version": "0.2.2",
            "provider": {"name": "Example", "url": "https://example.com"},
            "endpoint": "https://example.com/cap",
            "conformance_level": 2,
            "supported_verbs": {"core": ["graph.paths"], "convenience": []},
            "causal_engine": CapabilityCausalEngine(
                family="constraint_based",
                algorithm="PCMCI",
                structural_mechanisms=CapabilityStructuralMechanisms(
                    available=False,
                    families=[],
                    mechanism_override_supported=False,
                    counterfactual_ready=False,
                ),
            ),
            "detailed_capabilities": CapabilityDetailedCapabilities(
                graph_traversal=True,
                intervention_simulation=True,
                counterfactual_scm=False,
            ),
            "assumptions": ["causal_sufficiency"],
            "reasoning_modes_supported": ["graph_propagation"],
            "graph": {
                "domains": ["equities"],
                "node_count": 1,
                "edge_count": 0,
                "node_types": ["close_price"],
                "edge_types_supported": ["directed_lagged"],
                "graph_representation": "time_lagged_dag",
                "update_frequency": "PT24H",
                "coverage_description": "Example graph.",
            },
            "authentication": {"type": "none"},
            "access_tiers": [
                {
                    "tier": "public",
                    "verbs": ["graph.paths"],
                    "response_detail": "raw",
                    "hidden_fields": ["tau"],
                }
            ],
            "disclosure_policy": {
                "hidden_fields": ["tau"],
                "default_response_detail": "raw",
                "notes": ["example"],
            },
            "bindings": CapabilityBindings(
                mcp=CapabilityMCPBinding(enabled=True, endpoint="https://example.com/mcp"),
                a2a=CapabilityA2ABinding(
                    enabled=False,
                    agent_card_url="https://example.com/.well-known/agent-card.json",
                ),
            ),
        }
    )

    assert card.causal_engine is not None
    assert card.causal_engine.structural_mechanisms is not None
    assert card.causal_engine.structural_mechanisms.available is False
    assert card.detailed_capabilities is not None
    assert card.detailed_capabilities.intervention_simulation is True
    assert card.graph.temporal_resolution is None
    assert card.access_tiers[0].response_detail == "raw"
    assert card.disclosure_policy.default_response_detail == "raw"
    assert card.bindings is not None
    assert card.bindings.mcp is not None
    assert card.bindings.mcp.endpoint == "https://example.com/mcp"
    assert card.bindings.a2a is not None
    assert card.bindings.a2a.enabled is False


def test_protocol_success_response_builder_wraps_models_without_adapter_boilerplate() -> None:
    request_payload = build_graph_paths_request(
        source_node_id="NVDA_close",
        target_node_id="AMD_close",
        request_id="req-paths",
    )

    response_payload = build_cap_success_response(
        payload=request_payload,
        result=GraphPathsRequest.model_validate(
            {
                "cap_version": "0.2.2",
                "request_id": "ignored",
                "verb": "graph.paths",
                "params": {
                    "source_node_id": "NVDA_close",
                    "target_node_id": "AMD_close",
                    "max_paths": 3,
                },
            }
        ).params,
        provenance=AppCAPProvenance(
            algorithm=ALGORITHM_PCMCI,
            graph_version="CausalNodeV2",
            computation_time_ms=4,
            sample_size=144,
            server_name="abel-cap",
            server_version="0.1.0",
            cap_spec_version="0.2.2",
        ),
    )

    assert response_payload == {
        "cap_version": "0.2.2",
        "request_id": "req-paths",
        "verb": "graph.paths",
        "status": "success",
        "result": {
            "source_node_id": "NVDA_close",
            "target_node_id": "AMD_close",
            "max_paths": 3,
        },
        "provenance": {
            "algorithm": ALGORITHM_PCMCI,
            "graph_version": "CausalNodeV2",
            "computation_time_ms": 4,
            "sample_size": 144,
            "server_name": "abel-cap",
            "server_version": "0.1.0",
            "cap_spec_version": "0.2.2",
        },
    }


def test_cap_provenance_supports_optional_draft_gap_fields() -> None:
    provenance_with_optional = AppCAPProvenance(
        algorithm=ALGORITHM_PCMCI,
        graph_version="CausalNodeV2",
        graph_timestamp="2026-03-18T00:00:00Z",
        sample_size=128,
        computation_time_ms=4,
        server_name="abel-cap",
        server_version="0.1.0",
        cap_spec_version="0.2.2",
    )
    provenance_without_optional = AppCAPProvenance(
        algorithm=ALGORITHM_PCMCI,
        graph_version="CausalNodeV2",
        computation_time_ms=4,
        server_name="abel-cap",
        server_version="0.1.0",
        cap_spec_version="0.2.2",
    )

    assert provenance_with_optional.model_dump(exclude_none=True)["graph_timestamp"] == (
        "2026-03-18T00:00:00Z"
    )
    assert provenance_with_optional.model_dump(exclude_none=True)["sample_size"] == 128
    assert "graph_timestamp" not in provenance_without_optional.model_dump(exclude_none=True)
    assert "sample_size" not in provenance_without_optional.model_dump(exclude_none=True)


def test_app_dispatch_registry_drives_supported_verbs_surface() -> None:
    registry = build_dispatch_registry()
    supported_verbs = build_supported_verbs(registry)

    assert supported_verbs.model_dump() == {
        "core": [
            "meta.capabilities",
            "observe.predict",
            "intervene.do",
            "graph.neighbors",
            "graph.markov_blanket",
            "graph.paths",
        ],
        "convenience": [
            "traverse.parents",
            "traverse.children",
        ],
    }
    assert registry.extension_verbs_by_namespace == {
        "abel": [
            "extensions.abel.validate_connectivity",
            "extensions.abel.markov_blanket",
            "extensions.abel.counterfactual_preview",
            "extensions.abel.intervene_time_lag",
        ]
    }


def test_build_handler_success_wraps_result_and_provenance_from_request_payload() -> None:
    request_payload = build_graph_paths_request(
        source_node_id="NVDA_close",
        target_node_id="AMD_close",
        request_id="req-adapter",
    )

    response_payload = build_handler_success(
        payload=request_payload,
        result={"connected": True},
        provenance_factory=lambda: build_cap_provenance(
            context=CAPProvenanceContext(
                graph_version="CausalNodeV2",
                server_name="abel-cap",
                server_version="0.1.0",
            ),
            hint=CAPProvenanceHint(algorithm="primitive.explain"),
            computation_time_ms=4,
        ),
    )

    assert response_payload["cap_version"] == "0.2.2"
    assert response_payload["request_id"] == "req-adapter"
    assert response_payload["verb"] == "graph.paths"
    assert response_payload["status"] == "success"
    assert response_payload["result"] == {"connected": True}
    assert response_payload["provenance"]["algorithm"] == "primitive.explain"
    assert response_payload["provenance"]["server_name"]
    assert response_payload["provenance"]["computation_time_ms"] == 4


def test_build_cap_provenance_uses_context_and_omits_unset_optional_fields() -> None:
    provenance = build_cap_provenance(
        context=CAPProvenanceContext(
            graph_version="CausalNodeV2",
            server_name="abel-cap",
            server_version="0.1.0",
        ),
        hint=CAPProvenanceHint(
            algorithm=ALGORITHM_PCMCI,
            sample_size=256,
        ),
        computation_time_ms=7,
    )
    minimal_provenance = build_cap_provenance(
        context=CAPProvenanceContext(
            graph_version="CausalNodeV2",
            server_name="abel-cap",
            server_version="0.1.0",
        ),
        hint=CAPProvenanceHint(algorithm="primitive.predict"),
        computation_time_ms=3,
    )

    assert provenance.algorithm == ALGORITHM_PCMCI
    assert provenance.sample_size == 256
    assert provenance.mechanism_family_used is None
    assert provenance.server_name == "abel-cap"
    assert provenance.graph_version == "CausalNodeV2"
    assert provenance.computation_time_ms == 7
    assert "sample_size" not in minimal_provenance.model_dump(exclude_none=True)
    assert "graph_timestamp" not in minimal_provenance.model_dump(exclude_none=True)


def test_reduce_handler_success_autofills_shared_provenance_fields() -> None:
    request_payload = build_graph_paths_request(
        source_node_id="NVDA_close",
        target_node_id="AMD_close",
        request_id="req-reducer",
    )

    response_payload = reduce_handler_success(
        payload=request_payload,
        success=CAPHandlerSuccessSpec(
            result={"connected": True},
            provenance_hint=CAPProvenanceHint(
                algorithm="primitive.explain",
                graph_timestamp="2026-03-18T00:00:00Z",
            ),
        ),
        request=None,
        provenance_context=CAPProvenanceContext(
            graph_version="CausalNodeV2",
            server_name="abel-cap",
            server_version="0.1.0",
        ),
        computation_time_ms=9,
    )

    assert response_payload["cap_version"] == "0.2.2"
    assert response_payload["request_id"] == "req-reducer"
    assert response_payload["verb"] == "graph.paths"
    assert response_payload["status"] == "success"
    assert response_payload["result"] == {"connected": True}
    assert response_payload["provenance"] == {
        "algorithm": "primitive.explain",
        "graph_version": "CausalNodeV2",
        "graph_timestamp": "2026-03-18T00:00:00Z",
        "computation_time_ms": 9,
        "server_name": "abel-cap",
        "server_version": "0.1.0",
        "cap_spec_version": "0.2.2",
    }


def test_fastapi_dispatcher_reduces_handler_success_spec_with_context_provider() -> None:
    request_payload = build_graph_paths_request(
        source_node_id="a",
        target_node_id="b",
        request_id="req-dispatch-reduce",
    ).model_dump()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/cap",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    seen: dict[str, object] = {}

    def _handler_payload_request(typed_payload, current_request):
        seen["payload_verb"] = typed_payload.verb
        seen["request_path"] = current_request.url.path
        return CAPHandlerSuccessSpec(
            result={
                "source_node_id": "a",
                "target_node_id": "b",
                "connected": True,
                "path_count": 0,
                "paths": [],
                "reasoning_mode": REASONING_MODE_GRAPH_PROPAGATION,
                "identification_status": IDENTIFICATION_STATUS_NOT_APPLICABLE,
                "assumptions": [],
            },
            provenance_hint=CAPProvenanceHint(algorithm="primitive.explain"),
        )

    def _provenance_context_provider(typed_payload, current_request):
        seen["provider_payload_verb"] = typed_payload.verb
        seen["provider_request_path"] = current_request.url.path
        return CAPProvenanceContext(
            graph_version="CausalNodeV2",
            server_name="abel-cap",
            server_version="0.1.0",
        )

    async def _run() -> None:
        registry = CAPVerbRegistry()
        registry.register_core_contract(GRAPH_PATHS_CONTRACT, handler=_handler_payload_request)
        dispatcher = build_fastapi_cap_dispatcher(
            registry=registry,
            provenance_context_provider=_provenance_context_provider,
        )
        result = await dispatcher(request_payload, request)
        assert result["verb"] == "graph.paths"
        assert result["result"]["connected"] is True
        assert result["result"]["path_count"] == 0
        assert result["provenance"]["algorithm"] == "primitive.explain"
        assert result["provenance"]["server_name"] == "abel-cap"
        assert result["provenance"]["computation_time_ms"] >= 1

    asyncio.run(_run())

    assert seen == {
        "payload_verb": "graph.paths",
        "request_path": "/cap",
        "provider_payload_verb": "graph.paths",
        "provider_request_path": "/cap",
    }


def test_fastapi_dispatcher_passes_success_spec_to_custom_reducer() -> None:
    request_payload = build_graph_paths_request(source_node_id="a", target_node_id="b").model_dump()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/cap",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    seen: dict[str, object] = {}

    def _handler_payload_request(typed_payload, current_request):
        return CAPHandlerSuccessSpec(
            result={
                "source_node_id": "a",
                "target_node_id": "b",
                "connected": True,
                "path_count": 0,
                "paths": [],
                "reasoning_mode": REASONING_MODE_GRAPH_PROPAGATION,
                "identification_status": IDENTIFICATION_STATUS_NOT_APPLICABLE,
                "assumptions": [],
            },
            provenance_hint=CAPProvenanceHint(algorithm="primitive.explain"),
        )

    def _provenance_context_provider(typed_payload, current_request):
        return CAPProvenanceContext(
            graph_version="CausalNodeV2",
            server_name="abel-cap",
            server_version="0.1.0",
        )

    def _success_reducer(*, payload, success, request, provenance_context, computation_time_ms):
        seen["payload_verb"] = payload.verb
        seen["algorithm"] = success.provenance_hint.algorithm
        seen["server_name"] = provenance_context.server_name
        seen["request_path"] = request.url.path
        seen["computation_time_ms"] = computation_time_ms
        return build_cap_success_response(
            payload=payload,
            result=success.result,
            provenance={
                "algorithm": "custom.reducer",
                "graph_version": provenance_context.graph_version,
                "computation_time_ms": computation_time_ms,
                "server_name": provenance_context.server_name,
                "server_version": provenance_context.server_version,
                "cap_spec_version": provenance_context.cap_spec_version,
            },
        )

    async def _run() -> None:
        registry = CAPVerbRegistry()
        registry.register_core_contract(GRAPH_PATHS_CONTRACT, handler=_handler_payload_request)
        dispatcher = build_fastapi_cap_dispatcher(
            registry=registry,
            provenance_context_provider=_provenance_context_provider,
            success_reducer=_success_reducer,
        )
        result = await dispatcher(request_payload, request)
        assert result["provenance"]["algorithm"] == "custom.reducer"

    asyncio.run(_run())

    assert seen["payload_verb"] == "graph.paths"
    assert seen["algorithm"] == "primitive.explain"
    assert seen["server_name"] == "abel-cap"
    assert seen["request_path"] == "/cap"
    assert int(seen["computation_time_ms"]) >= 1


def test_fastapi_dispatcher_calls_registered_handler_with_payload_and_request() -> None:
    request_payload = build_graph_paths_request(source_node_id="a", target_node_id="b").model_dump()
    response_payload = {
        "cap_version": "0.2.2",
        "request_id": "req-paths",
        "verb": "graph.paths",
        "status": "success",
        "result": {
            "source_node_id": "a",
            "target_node_id": "b",
            "connected": True,
            "path_count": 0,
            "paths": [],
            "reasoning_mode": REASONING_MODE_GRAPH_PROPAGATION,
            "identification_status": IDENTIFICATION_STATUS_NOT_APPLICABLE,
            "assumptions": [],
        },
        "provenance": {
            "algorithm": "graph.paths",
            "graph_version": "CausalNodeV2",
            "computation_time_ms": 1,
            "server_name": "abel-cap",
            "server_version": "0.1.0",
            "cap_spec_version": "0.2.2",
        },
    }
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/cap",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )

    def _handler_payload_request(typed_payload, current_request):
        assert current_request.url.path == "/cap"
        assert typed_payload.verb == "graph.paths"
        return response_payload

    async def _run() -> None:
        registry = CAPVerbRegistry()
        registry.register_core_contract(GRAPH_PATHS_CONTRACT, handler=_handler_payload_request)
        dispatcher = build_fastapi_cap_dispatcher(registry=registry)
        result = await dispatcher(request_payload, request)
        assert result["verb"] == "graph.paths"

    asyncio.run(_run())


def test_app_layer_reuses_protocol_models_and_envelope_helpers() -> None:
    assert AppCapabilityCard is CapabilityCard
    assert AppGraphPathsRequest is GraphPathsRequest
    assert AppCAPProvenance is CAPProvenance


def test_async_client_posts_built_cap_payload_to_current_http_route() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert request.method == "POST"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "request_id": "req-neighbors",
            "options": {"response_detail": "summary"},
            "verb": "graph.neighbors",
            "params": {
                "node_id": "NVDA_close",
                "scope": "children",
                "max_neighbors": 2,
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-neighbors",
                "verb": "graph.neighbors",
                "status": "success",
                "result": {
                    "node_id": "NVDA_close",
                    "scope": "children",
                    "neighbors": [{"node_id": "AMD_close", "roles": ["child"]}],
                    "reasoning_mode": "identified_causal_effect",
                    "identification_status": "identified",
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                    "edge_semantics": "identified_causal_effect",
                    "total_candidate_count": 1,
                    "truncated": False,
                },
                "provenance": {
                    "algorithm": "graph.neighbors",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    async def _run() -> None:
        client = AsyncCAPClient(
            "https://cap.example",
            routes=DEFAULT_CAP_ROUTES,
            transport=httpx.MockTransport(_handler),
        )
        response = await client.graph_neighbors(
            node_id="NVDA_close",
            scope="children",
            max_neighbors=2,
            request_id="req-neighbors",
        )
        await client.aclose()

        assert response.result.neighbors[0].node_id == "AMD_close"

    asyncio.run(_run())


def test_async_client_can_send_request_level_headers_to_cap_server() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer request-key"
        assert request.headers["X-Trace-ID"] == "trace-123"
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-meta",
                "verb": "meta.capabilities",
                "status": "success",
                "result": {
                    "$schema": "https://causalagentprotocol.org/schema/capability-card/v0.2.2.json",
                    "name": "Abel CAP Test",
                    "description": "Capability card used by protocol client tests.",
                    "version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                    "provider": {"name": "Abel AI", "url": "https://abel.ai"},
                    "endpoint": "https://cap.example/cap",
                    "conformance_level": 1,
                    "supported_verbs": {"core": ["meta.capabilities"], "convenience": []},
                    "assumptions": [],
                    "reasoning_modes_supported": [],
                    "graph": {
                        "domains": [],
                        "node_count": 1,
                        "edge_count": 0,
                        "node_types": [],
                        "edge_types_supported": [],
                        "graph_representation": "time_lagged_directed_graph",
                        "update_frequency": "unknown",
                        "temporal_resolution": "unknown",
                        "coverage_description": "test fixture",
                    },
                    "authentication": {"type": "api_key", "details": {}},
                    "access_tiers": [],
                    "disclosure_policy": {
                        "hidden_fields": [],
                        "default_response_detail": "summary",
                        "notes": [],
                    },
                },
            },
        )

    async def _run() -> None:
        client = AsyncCAPClient(
            "https://cap.example",
            routes=DEFAULT_CAP_ROUTES,
            transport=httpx.MockTransport(_handler),
        )
        response = await client.meta_capabilities(
            request_id="req-meta",
            headers={
                "Authorization": "Bearer request-key",
                "X-Trace-ID": "trace-123",
            },
        )
        await client.aclose()

        assert response.verb == "meta.capabilities"

    asyncio.run(_run())


def test_async_client_can_map_route_alias_to_cap_verb() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "intervene.do",
            "params": {
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "outcome_node": "AMD_close",
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-intervene",
                "verb": "intervene.do",
                "status": "success",
                "result": {
                    "reasoning_mode": REASONING_MODE_GRAPH_PROPAGATION,
                    "outcome_node": "AMD_close",
                    "effect": 0.12,
                    "identification_status": IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                "provenance": {
                    "algorithm": ALGORITHM_PCMCI,
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "mechanism_family_used": "linear_scm",
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    async def _run() -> None:
        client = AsyncCAPClient(
            "https://cap.example",
            routes=DEFAULT_CAP_ROUTES,
            transport=httpx.MockTransport(_handler),
        )
        response = await client.request_route(
            "intervene/do",
            params={
                "treatment_node": "NVDA_close",
                "treatment_value": 0.05,
                "outcome_node": "AMD_close",
            },
            response_model=InterveneDoResponse,
        )
        await client.aclose()

        assert response.result.outcome_node == "AMD_close"
        assert response.result.reasoning_mode == REASONING_MODE_GRAPH_PROPAGATION
        assert response.result.effect == 0.12
        assert "outcome_summary" not in response.result.model_dump(exclude_none=True)
        assert "node_summaries" not in response.result.model_dump(exclude_none=True)
        assert (
            response.result.identification_status == IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED
        )

    asyncio.run(_run())


def test_async_client_markov_blanket_uses_unified_graph_neighbors_scope() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "graph.markov_blanket",
            "params": {
                "node_id": "NVDA_close",
                "max_neighbors": 10,
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-markov-blanket",
                "verb": "graph.markov_blanket",
                "status": "success",
                "result": {
                    "node_id": "NVDA_close",
                    "neighbors": [
                        {"node_id": "SOXX_close", "roles": ["parent"]},
                        {"node_id": "QQQ_close", "roles": ["spouse"]},
                    ],
                    "reasoning_mode": REASONING_MODE_STRUCTURAL_SEMANTICS,
                    "identification_status": IDENTIFICATION_STATUS_NOT_APPLICABLE,
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                    "edge_semantics": "markov_blanket_membership",
                    "total_candidate_count": 2,
                    "truncated": False,
                },
                "provenance": {
                    "algorithm": "primitive.explain",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    async def _run() -> None:
        client = AsyncCAPClient(
            "https://cap.example",
            routes=DEFAULT_CAP_ROUTES,
            transport=httpx.MockTransport(_handler),
        )
        response = await client.graph_markov_blanket(
            node_id="NVDA_close",
            max_neighbors=10,
        )
        await client.aclose()

        assert response.result.neighbors[1].roles == ["spouse"]

    asyncio.run(_run())


def test_async_client_traverse_parents_uses_verb_specific_params() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "traverse.parents",
            "params": {
                "node_id": "NVDA_close",
                "top_k": 3,
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-traverse-parents",
                "verb": "traverse.parents",
                "status": "success",
                "result": {
                    "node_id": "NVDA_close",
                    "direction": "parents",
                    "nodes": ["SOXX_close", "QQQ_close"],
                    "reasoning_mode": REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
                    "identification_status": "identified",
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                "provenance": {
                    "algorithm": "primitive.explain",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    async def _run() -> None:
        client = AsyncCAPClient(
            "https://cap.example",
            routes=DEFAULT_CAP_ROUTES,
            transport=httpx.MockTransport(_handler),
        )
        response = await client.traverse_parents(node_id="NVDA_close", top_k=3)
        await client.aclose()

        assert response.result.direction == "parents"
        assert response.result.nodes == ["SOXX_close", "QQQ_close"]

    asyncio.run(_run())


def test_async_client_traverse_children_uses_verb_specific_params() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "options": {"response_detail": "summary"},
            "verb": "traverse.children",
            "params": {
                "node_id": "NVDA_close",
                "top_k": 2,
            },
        }
        return httpx.Response(
            200,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-traverse-children",
                "verb": "traverse.children",
                "status": "success",
                "result": {
                    "node_id": "NVDA_close",
                    "direction": "children",
                    "nodes": ["AMD_close"],
                    "reasoning_mode": REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
                    "identification_status": "identified",
                    "assumptions": [ASSUMPTION_CAUSAL_SUFFICIENCY],
                },
                "provenance": {
                    "algorithm": "primitive.explain",
                    "graph_version": "CausalNodeV2",
                    "computation_time_ms": 8,
                    "server_name": "abel-cap",
                    "server_version": "0.1.0",
                    "cap_spec_version": "0.2.2",
                },
            },
        )

    async def _run() -> None:
        client = AsyncCAPClient(
            "https://cap.example",
            routes=DEFAULT_CAP_ROUTES,
            transport=httpx.MockTransport(_handler),
        )
        response = await client.traverse_children(node_id="NVDA_close", top_k=2)
        await client.aclose()

        assert response.result.direction == "children"
        assert response.result.nodes == ["AMD_close"]

    asyncio.run(_run())


def test_async_client_raises_cap_http_error_with_parsed_error_body() -> None:
    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/cap"
        assert json.loads(request.content.decode("utf-8")) == {
            "cap_version": "0.2.2",
            "request_id": "req-meta",
            "options": {"response_detail": "summary"},
            "verb": "meta.capabilities",
        }
        return httpx.Response(
            503,
            json={
                "cap_version": "0.2.2",
                "request_id": "req-meta",
                "verb": "meta.capabilities",
                "status": "error",
                "error": {
                    "code": "service_unavailable",
                    "message": "Capability card backend is unavailable.",
                    "details": {"upstream": "gateway"},
                },
            },
        )

    async def _run() -> None:
        client = AsyncCAPClient(
            "https://cap.example",
            routes=DEFAULT_CAP_ROUTES,
            transport=httpx.MockTransport(_handler),
        )
        with pytest.raises(CAPHTTPError) as exc_info:
            await client.meta_capabilities(request_id="req-meta")
        await client.aclose()

        assert exc_info.value.status_code == 503
        assert exc_info.value.cap_error is not None
        assert exc_info.value.cap_error.code == "service_unavailable"

    asyncio.run(_run())
