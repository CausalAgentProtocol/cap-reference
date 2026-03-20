from __future__ import annotations

from collections.abc import Mapping

from abel_cap_server.cap.adapters.common import (
    build_upstream_request_kwargs,
    require_supported_graph_ref,
    sanitize_upstream_payload,
)
from abel_cap_server.cap.disclosure import INTERVENTIONAL_ASSUMPTIONS
from abel_cap_server.cap.errors import translate_upstream_error
from abel_cap_server.clients.abel_gateway_client import AbelGatewayClient
from cap.core import (
    ALGORITHM_PCMCI,
    IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
    REASONING_MODE_GRAPH_PROPAGATION,
)
from cap.core.contracts import InterveneDoRequest, InterveneDoResult
from cap.server import CAPAdapterError, CAPHandlerSuccessSpec, CAPProvenanceHint


DEFAULT_INTERVENTION_MECHANISM_FAMILY = "linear_scm"
DEFAULT_INTERVENTION_HORIZON_STEPS = 24


async def intervene_do(
    primitive_client: AbelGatewayClient,
    payload: InterveneDoRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)

    try:
        raw = await primitive_client.intervene(
            {
                **payload.params.model_dump(),
                "model": "linear",
                "horizon_steps": DEFAULT_INTERVENTION_HORIZON_STEPS,
            },
            **build_upstream_request_kwargs(
                timeout_ms=payload.options.timeout_ms,
                headers=headers,
            ),
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="intervene") from exc

    sanitized = sanitize_upstream_payload(raw)
    effect_value = _resolve_effect_value(sanitized, payload.params.outcome_node)
    if effect_value is None:
        raise CAPAdapterError(
            "path_not_found",
            f"No propagated effect was returned for outcome_node={payload.params.outcome_node!r}.",
            status_code=404,
        )

    result = InterveneDoResult(
        reasoning_mode=REASONING_MODE_GRAPH_PROPAGATION,
        outcome_node=payload.params.outcome_node,
        effect=effect_value,
        identification_status=IDENTIFICATION_STATUS_NOT_FORMALLY_IDENTIFIED,
        assumptions=INTERVENTIONAL_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(
            algorithm=ALGORITHM_PCMCI,
            mechanism_family_used=DEFAULT_INTERVENTION_MECHANISM_FAMILY,
        ),
    )


def _resolve_effect_value(sanitized: dict, outcome_node: str) -> float | None:
    for item in sanitized.get("node_summaries", []):
        if isinstance(item, dict) and item.get("node_id") == outcome_node:
            value = item.get("final_cumulative_effect")
            if value is not None:
                return float(value)

    return None
