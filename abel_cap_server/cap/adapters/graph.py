from __future__ import annotations

from collections.abc import Mapping
from collections import defaultdict
from typing import Literal, cast

from abel_cap_server.cap.adapters.common import (
    build_upstream_request_kwargs,
    require_supported_graph_ref,
    sanitize_upstream_payload,
)
from abel_cap_server.cap.contracts import (
    AbelGraphPath,
    AbelGraphPathEdge,
    AbelGraphPathsResult,
)
from abel_cap_server.cap.disclosure import STRUCTURAL_ASSUMPTIONS
from abel_cap_server.cap.errors import translate_upstream_error
from abel_cap_server.clients.abel_gateway_client import AbelGatewayClient
from cap.core import (
    ALGORITHM_PCMCI,
    IDENTIFICATION_STATUS_IDENTIFIED,
    IDENTIFICATION_STATUS_NOT_APPLICABLE,
    REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
    REASONING_MODE_STRUCTURAL_SEMANTICS,
)
from cap.core.contracts import (
    GraphNeighbor,
    GraphMarkovBlanketRequest,
    GraphMarkovBlanketResult,
    GraphNeighborsRequest,
    GraphNeighborsResult,
    GraphPathNode,
    GraphPathsRequest,
    TraverseChildrenRequest,
    TraverseParentsRequest,
    TraverseResult,
)
from cap.server import CAPHandlerSuccessSpec, CAPProvenanceHint


async def graph_neighbors(
    primitive_client: AbelGatewayClient,
    payload: GraphNeighborsRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)
    scope = payload.params.scope
    raw = await _run_explain(
        primitive_client,
        payload.params.node_id,
        scope,
        payload.options.timeout_ms,
        headers=headers,
    )
    sanitized = sanitize_upstream_payload(raw)
    candidate_neighbors = _map_neighbors_from_scope(scope, sanitized)
    total_candidate_count = len(candidate_neighbors)
    neighbors = candidate_neighbors
    if payload.params.max_neighbors > 0:
        neighbors = neighbors[: payload.params.max_neighbors]

    result = GraphNeighborsResult(
        node_id=payload.params.node_id,
        scope=scope,
        neighbors=neighbors,
        total_candidate_count=total_candidate_count,
        truncated=total_candidate_count > len(neighbors),
        edge_semantics="identified_causal_effect",
        reasoning_mode=REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
        identification_status=IDENTIFICATION_STATUS_IDENTIFIED,
        assumptions=STRUCTURAL_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm="primitive.explain"),
    )


async def graph_markov_blanket(
    primitive_client: AbelGatewayClient,
    payload: GraphMarkovBlanketRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)
    raw = await _run_explain(
        primitive_client,
        payload.params.node_id,
        "markov_blanket",
        payload.options.timeout_ms,
        headers=headers,
    )
    sanitized = sanitize_upstream_payload(raw)
    candidate_neighbors = _map_neighbors_from_scope("markov_blanket", sanitized)
    total_candidate_count = len(candidate_neighbors)
    neighbors = candidate_neighbors
    if payload.params.max_neighbors > 0:
        neighbors = neighbors[: payload.params.max_neighbors]

    result = GraphMarkovBlanketResult(
        node_id=payload.params.node_id,
        neighbors=neighbors,
        total_candidate_count=total_candidate_count,
        truncated=total_candidate_count > len(neighbors),
        edge_semantics="markov_blanket_membership",
        reasoning_mode=REASONING_MODE_STRUCTURAL_SEMANTICS,
        identification_status=IDENTIFICATION_STATUS_NOT_APPLICABLE,
        assumptions=STRUCTURAL_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm="primitive.explain"),
    )


async def graph_paths(
    primitive_client: AbelGatewayClient,
    payload: GraphPathsRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)
    try:
        raw = await primitive_client.fetch_schema_paths(
            source_node_id=payload.params.source_node_id,
            target_node_id=payload.params.target_node_id,
            **build_upstream_request_kwargs(
                timeout_ms=payload.options.timeout_ms,
                headers=headers,
            ),
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="schema.paths") from exc

    raw_paths = raw.get("paths", [])
    trimmed_paths = raw_paths[: payload.params.max_paths]
    result = AbelGraphPathsResult(
        source_node_id=payload.params.source_node_id,
        target_node_id=payload.params.target_node_id,
        connected=bool(raw.get("connected", False)),
        path_count=len(trimmed_paths),
        paths=[_map_path(path) for path in trimmed_paths],
        reasoning_mode=REASONING_MODE_STRUCTURAL_SEMANTICS,
        identification_status=IDENTIFICATION_STATUS_NOT_APPLICABLE,
        assumptions=STRUCTURAL_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm=raw.get("method", ALGORITHM_PCMCI)),
    )


async def traverse_parents(
    primitive_client: AbelGatewayClient,
    payload: TraverseParentsRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    return await _traverse(primitive_client, payload, direction="parents", headers=headers)


async def traverse_children(
    primitive_client: AbelGatewayClient,
    payload: TraverseChildrenRequest,
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    return await _traverse(primitive_client, payload, direction="children", headers=headers)


async def _traverse(
    primitive_client: AbelGatewayClient,
    payload: TraverseParentsRequest | TraverseChildrenRequest,
    *,
    direction: Literal["parents", "children"],
    headers: Mapping[str, str] | None = None,
) -> CAPHandlerSuccessSpec:
    require_supported_graph_ref(payload)
    raw = await _run_explain(
        primitive_client,
        payload.params.node_id,
        direction,
        payload.options.timeout_ms,
        headers=headers,
    )
    sanitized = sanitize_upstream_payload(raw)
    nodes = sorted(set(sanitized.get("related_nodes", [])))
    if payload.params.top_k > 0:
        nodes = nodes[: payload.params.top_k]

    result = TraverseResult(
        node_id=payload.params.node_id,
        direction=cast(Literal["parents", "children"], direction),
        nodes=nodes,
        reasoning_mode=REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
        identification_status=IDENTIFICATION_STATUS_IDENTIFIED,
        assumptions=STRUCTURAL_ASSUMPTIONS,
    )
    return CAPHandlerSuccessSpec(
        result=result,
        provenance_hint=CAPProvenanceHint(algorithm="primitive.explain"),
    )


async def _run_explain(
    primitive_client: AbelGatewayClient,
    node_id: str,
    explain_scope: str,
    timeout_ms: int | None,
    headers: Mapping[str, str] | None = None,
) -> dict:
    try:
        return await primitive_client.explain(
            {
                "target_node": node_id,
                "scope": explain_scope,
            },
            **build_upstream_request_kwargs(timeout_ms=timeout_ms, headers=headers),
        )
    except Exception as exc:
        raise translate_upstream_error(exc, operation="explain") from exc


def _map_neighbors_from_scope(
    scope: Literal["parents", "children", "markov_blanket"],
    raw: dict,
) -> list[GraphNeighbor]:
    if "neighbors" in raw:
        structured = []
        for item in raw.get("neighbors", []):
            roles = _normalize_roles(item)
            structured.append(GraphNeighbor(node_id=item["node_id"], roles=roles))
        return sorted(structured, key=lambda item: (item.node_id, item.roles))

    if scope == "parents":
        return [
            GraphNeighbor(node_id=node_id, roles=["parent"])
            for node_id in sorted(set(raw.get("related_nodes", [])))
        ]
    if scope == "children":
        return [
            GraphNeighbor(node_id=node_id, roles=["child"])
            for node_id in sorted(set(raw.get("related_nodes", [])))
        ]

    role_map: dict[str, set[Literal["parent", "child", "spouse"]]] = defaultdict(set)
    for node_id in raw.get("parents", []):
        role_map[node_id].add("parent")
    for node_id in raw.get("children", []):
        role_map[node_id].add("child")
    for node_id in raw.get("spouses", []):
        role_map[node_id].add("spouse")

    if not role_map:
        for node_id in raw.get("related_nodes", []):
            role_map[node_id]

    return [
        GraphNeighbor(node_id=node_id, roles=sorted(roles))
        for node_id, roles in sorted(role_map.items())
    ]


def _normalize_roles(item: dict) -> list[Literal["parent", "child", "spouse"]]:
    if "roles" in item:
        roles = item.get("roles", [])
    elif "relationship" in item:
        roles = [item.get("relationship")]
    else:
        roles = []
    normalized = [
        cast(Literal["parent", "child", "spouse"], role)
        for role in roles
        if role in {"parent", "child", "spouse"}
    ]
    return cast(list[Literal["parent", "child", "spouse"]], sorted(set(normalized)))


def _map_path(raw_path: dict) -> AbelGraphPath:
    edges = [
        AbelGraphPathEdge(
            from_node_id=edge["from_node_id"],
            to_node_id=edge["to_node_id"],
            edge_type=edge.get("edge_type", "causes"),
            tau=_optional_int(edge.get("tau")),
            tau_duration=_tau_duration(_optional_int(edge.get("tau"))),
        )
        for edge in raw_path.get("edges", [])
    ]
    nodes = [
        GraphPathNode(
            node_id=node["node_id"],
            node_name=node.get("display_name", node["node_id"]),
            node_type=node.get("metric_type", "other"),
            domain=node.get("domain", "other"),
        )
        for node in raw_path.get("nodes", [])
    ]
    return AbelGraphPath(
        distance=int(raw_path.get("distance", len(edges))),
        nodes=nodes,
        edges=edges,
    )


def _tau_duration(tau: int | None) -> str | None:
    if tau is None:
        return None
    return f"PT{tau}H"


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)
