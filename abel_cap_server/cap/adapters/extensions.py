from __future__ import annotations

from collections.abc import Mapping

from abel_cap_server.cap.adapters.common import (
    build_upstream_request_kwargs,
    require_supported_graph_ref,
    sanitize_upstream_payload,
)
from abel_cap_server.cap.contracts import (
    CAPValidateInvalidVariable,
    CAPValidatePairResult,
    CounterfactualObserveDelta,
    ExtensionsCounterfactualPreviewRequest,
    ExtensionsCounterfactualPreviewResult,
    ExtensionsInterveneTimeLagRequest,
    ExtensionsInterveneTimeLagResult,
    ExtensionsMarkovBlanketRequest,
    ExtensionsMarkovBlanketResult,
    ExtensionsValidateConnectivityRequest,
    ExtensionsValidateConnectivityResult,
    TimeLagEffectSummary,
)
from abel_cap_server.cap.disclosure import (
    COUNTERFACTUAL_PREVIEW_ASSUMPTIONS,
    INTERVENTIONAL_ASSUMPTIONS,
    STRUCTURAL_ASSUMPTIONS,
    VALIDATION_ASSUMPTIONS,
)
from abel_cap_server.cap.errors import translate_upstream_error
from abel_cap_server.clients.abel_gateway_client import AbelGatewayClient
from cap.core import (
    ALGORITHM_PCMCI,
    IDENTIFICATION_STATUS_NOT_APPLICABLE,
    IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
    REASONING_MODE_GRAPH_PROPAGATION,
    REASONING_MODE_STRUCTURAL_SEMANTICS,
    REASONING_MODE_VALIDATION_GATE,
)
from cap.server import CAPAdapterError, CAPHandlerSuccessSpec, CAPProvenanceHint

from abel_cap_server.cap.adapters.graph import _map_neighbors_from_scope, _run_explain


DEFAULT_VALIDATE_CONNECTIVITY_MODE = "iv_gate"
DEFAULT_COUNTERFACTUAL_MECHANISM_FAMILY = "linear_scm"


async def validate_connectivity(
    primitive_client: AbelGatewayClient,
    payload: ExtensionsValidateConnectivityRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)

    try:
        raw = await primitive_client.validate(
            {
                **payload.params.model_dump(),
                "validation_mode": DEFAULT_VALIDATE_CONNECTIVITY_MODE,
            },
            **build_upstream_request_kwargs(
                timeout_ms=payload.options.timeout_ms,
                headers=headers,
            ),
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="validate") from exc

    sanitized = sanitize_upstream_payload(raw)
    result = ExtensionsValidateConnectivityResult(
        validation_method=sanitized.get("validation_method", "shortest_path_connectivity_proxy"),
        passed=bool(sanitized.get("passed", False)),
        valid_variables=list(sanitized.get("valid_variables", [])),
        invalid_variables=[
            CAPValidateInvalidVariable(**item) for item in sanitized.get("invalid_variables", [])
        ],
        pair_results=[CAPValidatePairResult(**item) for item in sanitized.get("pair_results", [])],
        reasoning_mode=REASONING_MODE_VALIDATION_GATE,
        identification_status=IDENTIFICATION_STATUS_NOT_APPLICABLE,
        assumptions=VALIDATION_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm="primitive.validate"),
    )


async def markov_blanket(
    primitive_client: AbelGatewayClient,
    payload: ExtensionsMarkovBlanketRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)
    try:
        raw = await _run_explain(
            primitive_client,
            payload.params.target_node,
            "markov_blanket",
            payload.options.timeout_ms,
            headers=headers,
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="explain") from exc

    sanitized = sanitize_upstream_payload(raw)
    neighbors = _map_neighbors_from_scope("markov_blanket", sanitized)
    result = ExtensionsMarkovBlanketResult(
        target_node=sanitized.get("target_node", payload.params.target_node),
        drivers=[neighbor.node_id for neighbor in neighbors if "parent" in neighbor.roles],
        markov_blanket=[neighbor.node_id for neighbor in neighbors],
        reasoning_mode=REASONING_MODE_STRUCTURAL_SEMANTICS,
        identification_status=IDENTIFICATION_STATUS_NOT_APPLICABLE,
        assumptions=STRUCTURAL_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm="primitive.explain"),
    )


async def counterfactual_preview(
    primitive_client: AbelGatewayClient,
    payload: ExtensionsCounterfactualPreviewRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)

    try:
        raw = await primitive_client.counterfactual(
            {
                **payload.params.model_dump(),
                "model": "linear",
            },
            **build_upstream_request_kwargs(
                timeout_ms=payload.options.timeout_ms,
                headers=headers,
            ),
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="counterfactual") from exc

    sanitized = sanitize_upstream_payload(raw)
    meta = sanitized.get("meta", {})
    reachable = bool(meta.get("reachable", False))
    observe_payload = sanitized.get("observe", {})
    # This preview still returns one implied counterfactual claim, so honesty
    # remains result-scoped until the surface grows explicit claim objects.
    result = ExtensionsCounterfactualPreviewResult(
        intervene_node=sanitized.get("intervene_node", payload.params.intervene_node),
        observe_node=sanitized.get("observe_node", payload.params.observe_node),
        intervene=dict(sanitized.get("intervene", {})),
        observe=CounterfactualObserveDelta(
            factual_value=observe_payload.get("original_value"),
            counterfactual_value=observe_payload.get("new_value"),
            change=observe_payload.get("change"),
        ),
        effect_support="reachable" if reachable else "no_structural_path",
        reachable=reachable,
        path_count=int(meta.get("path_count", 0)),
        reasoning_mode=REASONING_MODE_GRAPH_PROPAGATION,
        identification_status=IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
        assumptions=COUNTERFACTUAL_PREVIEW_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(
            algorithm=ALGORITHM_PCMCI,
            mechanism_family_used=DEFAULT_COUNTERFACTUAL_MECHANISM_FAMILY,
        ),
    )


async def intervene_time_lag(
    primitive_client: AbelGatewayClient,
    payload: ExtensionsInterveneTimeLagRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    if payload.params.model != "linear":
        raise CAPAdapterError(
            "invalid_intervention",
            "Only model=linear is supported by the current time-lag intervention extension.",
            status_code=400,
        )

    try:
        raw = await primitive_client.intervene(
            payload.params.model_dump(),
            **build_upstream_request_kwargs(
                timeout_ms=payload.options.timeout_ms,
                headers=headers,
            ),
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="intervene") from exc

    sanitized = sanitize_upstream_payload(raw)
    summaries = [
        TimeLagEffectSummary(
            node_id=item["node_id"],
            final_cumulative_effect=float(item["final_cumulative_effect"]),
            first_arrive_step=int(item["first_arrive_step"]),
            last_arrive_step=int(item["last_arrive_step"]),
            event_count=int(item["event_count"]),
            mechanism_coverage_complete=None,
        )
        for item in sanitized.get("node_summaries", [])
    ]
    outcome_summary = next(
        (item for item in summaries if item.node_id == payload.params.outcome_node), None
    )
    if outcome_summary is None:
        raise CAPAdapterError(
            "path_not_found",
            f"No propagated effect was returned for outcome_node={payload.params.outcome_node!r}.",
            status_code=404,
        )

    result = ExtensionsInterveneTimeLagResult(
        treatment_node=sanitized.get("treatment_node", payload.params.treatment_node),
        treatment_value=float(sanitized.get("treatment_value", payload.params.treatment_value)),
        model=sanitized.get("model", payload.params.model),
        delta_unit=str(sanitized.get("delta_unit", "logreturn")),
        horizon_steps=int(sanitized.get("horizon_steps", payload.params.horizon_steps)),
        outcome_node=payload.params.outcome_node,
        reasoning_mode=REASONING_MODE_GRAPH_PROPAGATION,
        outcome_summary=outcome_summary,
        total_events=int(sanitized.get("total_events", 0)),
        identification_status=IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
        assumptions=INTERVENTIONAL_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm=ALGORITHM_PCMCI),
    )
