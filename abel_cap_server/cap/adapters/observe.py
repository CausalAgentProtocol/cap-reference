from __future__ import annotations

from collections.abc import Mapping

from abel_cap_server.cap.adapters.common import (
    build_upstream_request_kwargs,
    require_supported_graph_ref,
    sanitize_upstream_payload,
)
from abel_cap_server.cap.errors import translate_upstream_error
from abel_cap_server.clients.abel_gateway_client import AbelGatewayClient
from cap.core.contracts import ObservePredictRequest, ObservePredictResult
from cap.server import CAPHandlerSuccessSpec, CAPProvenanceHint


async def observe_predict(
    primitive_client: AbelGatewayClient,
    payload: ObservePredictRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)
    requested_model = "linear"
    requested_feature_type = "parents"

    try:
        raw = await primitive_client.predict(
            {
                "target_node": payload.params.target_node,
                "model": requested_model,
                "feature_type": requested_feature_type,
            },
            **build_upstream_request_kwargs(
                timeout_ms=payload.options.timeout_ms,
                headers=headers,
            ),
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="predict") from exc

    sanitized = sanitize_upstream_payload(raw)
    result = ObservePredictResult(
        target_node=sanitized.get("target_node", payload.params.target_node),
        prediction=float(sanitized.get("prediction", 0.0)),
        drivers=list(sanitized.get("drivers", [])),
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm="primitive.predict"),
    )
