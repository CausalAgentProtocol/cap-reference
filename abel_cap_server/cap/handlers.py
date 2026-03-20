from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from fastapi import Request

from abel_cap_server.cap.contracts import (
    ExtensionsCounterfactualPreviewRequest,
    ExtensionsInterveneTimeLagRequest,
    ExtensionsMarkovBlanketRequest,
    ExtensionsValidateConnectivityRequest,
)
from cap.core.contracts import (
    GraphMarkovBlanketRequest,
    GraphNeighborsRequest,
    GraphPathsRequest,
    InterveneDoRequest,
    MetaCapabilitiesRequest,
    ObservePredictRequest,
    TraverseChildrenRequest,
    TraverseParentsRequest,
)

if TYPE_CHECKING:
    from abel_cap_server.cap.service import CapService


def get_cap_service_from_request(request: Request) -> CapService:
    return cast("CapService", request.app.state.cap_service)


def meta_capabilities(payload: MetaCapabilitiesRequest, request: Request) -> dict:
    service = get_cap_service_from_request(request)
    return service.build_capabilities_envelope(
        payload.request_id, str(request.base_url)
    ).model_dump(
        exclude_none=True,
        by_alias=True,
    )


async def observe_predict(payload: ObservePredictRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).observe_predict(payload, request.headers)


async def intervene_do(payload: InterveneDoRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).intervene_do(payload, request.headers)


async def graph_neighbors(payload: GraphNeighborsRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).graph_neighbors(payload, request.headers)


async def graph_markov_blanket(payload: GraphMarkovBlanketRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).graph_markov_blanket(
        payload, request.headers
    )


async def graph_paths(payload: GraphPathsRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).graph_paths(payload, request.headers)


async def traverse_parents(payload: TraverseParentsRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).traverse_parents(payload, request.headers)


async def traverse_children(payload: TraverseChildrenRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).traverse_children(payload, request.headers)


async def validate_connectivity(
    payload: ExtensionsValidateConnectivityRequest,
    request: Request,
) -> dict:
    return await get_cap_service_from_request(request).validate_connectivity(
        payload, request.headers
    )


async def markov_blanket(payload: ExtensionsMarkovBlanketRequest, request: Request) -> dict:
    return await get_cap_service_from_request(request).markov_blanket(payload, request.headers)


async def counterfactual_preview(
    payload: ExtensionsCounterfactualPreviewRequest,
    request: Request,
) -> dict:
    return await get_cap_service_from_request(request).counterfactual_preview(
        payload, request.headers
    )


async def intervene_time_lag(
    payload: ExtensionsInterveneTimeLagRequest,
    request: Request,
) -> dict:
    return await get_cap_service_from_request(request).intervene_time_lag(
        payload, request.headers
    )
