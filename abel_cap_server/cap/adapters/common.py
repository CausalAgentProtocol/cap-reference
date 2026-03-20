from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from abel_cap_server.cap.catalog import DEFAULT_CAP_GRAPH_PROFILE
from cap.core import CAPGraphRef
from cap.core.envelopes import CAPRequestBase
from cap.server import CAPAdapterError
from abel_cap_server.cap.disclosure import sanitize_hidden_fields


def sanitize_upstream_payload(payload: Any) -> Any:
    return sanitize_hidden_fields(payload)


def build_upstream_request_kwargs(
    *,
    timeout_ms: int | None,
    headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"timeout_ms": timeout_ms}
    if headers is not None:
        kwargs["headers"] = headers
    return kwargs


def require_supported_graph_ref(payload: CAPRequestBase) -> CAPGraphRef | None:
    graph_ref = None if payload.context is None else payload.context.graph_ref
    if graph_ref is None:
        return None

    if graph_ref.graph_id is not None and graph_ref.graph_id != DEFAULT_CAP_GRAPH_PROFILE.graph_id:
        raise CAPAdapterError(
            "invalid_request",
            f"graph_id={graph_ref.graph_id!r} is not supported by this CAP server.",
            status_code=400,
            details={"supported_graph_id": DEFAULT_CAP_GRAPH_PROFILE.graph_id},
        )
    if (
        graph_ref.graph_version is not None
        and graph_ref.graph_version != DEFAULT_CAP_GRAPH_PROFILE.graph_version
    ):
        raise CAPAdapterError(
            "invalid_request",
            f"graph_version={graph_ref.graph_version!r} is not supported by this CAP server.",
            status_code=400,
            details={"supported_graph_version": DEFAULT_CAP_GRAPH_PROFILE.graph_version},
        )
    return graph_ref


__all__ = [
    "build_upstream_request_kwargs",
    "require_supported_graph_ref",
    "sanitize_upstream_payload",
]
