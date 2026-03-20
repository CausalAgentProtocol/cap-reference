from __future__ import annotations

from collections.abc import Mapping

from abel_cap_server.cap.adapters import (
    counterfactual_preview,
    graph_markov_blanket,
    graph_neighbors,
    graph_paths,
    intervene_do,
    intervene_time_lag,
    markov_blanket,
    observe_predict,
    traverse_children,
    traverse_parents,
    validate_connectivity,
)
from abel_cap_server.cap.catalog import (
    CapabilityCard,
    build_capability_card,
    server_identity_from_settings,
)
from abel_cap_server.cap.contracts import (
    ExtensionsCounterfactualPreviewRequest,
    ExtensionsInterveneTimeLagRequest,
    ExtensionsMarkovBlanketRequest,
    ExtensionsValidateConnectivityRequest,
)
from abel_cap_server.cap.provenance import build_abel_provenance_context
from abel_cap_server.clients.abel_gateway_client import AbelGatewayClient
from abel_cap_server.core.config import Settings
from cap.core.constants import CAP_VERSION
from cap.core.contracts import (
    GraphMarkovBlanketRequest,
    GraphNeighborsRequest,
    GraphPathsRequest,
    InterveneDoRequest,
    MetaCapabilitiesResponse,
    ObservePredictRequest,
    TraverseChildrenRequest,
    TraverseParentsRequest,
)
from cap.core.envelopes import normalize_request_id
from cap.server import CAPProvenanceContext


class CapService:
    def __init__(self, settings: Settings, primitive_client: AbelGatewayClient) -> None:
        self._settings = settings
        self._server_identity = server_identity_from_settings(settings)
        self._primitive_client = primitive_client

    def build_capability_card(self, public_base_url: str) -> CapabilityCard:
        return build_capability_card(self._settings, public_base_url=public_base_url)

    def build_capabilities_envelope(
        self, request_id: str | None, public_base_url: str
    ) -> MetaCapabilitiesResponse:
        return MetaCapabilitiesResponse(
            cap_version=CAP_VERSION,
            request_id=normalize_request_id(request_id),
            verb="meta.capabilities",
            status="success",
            result=self.build_capability_card(public_base_url),
        )

    def build_provenance_context(self) -> CAPProvenanceContext:
        return build_abel_provenance_context(self._server_identity)

    async def observe_predict(
        self,
        payload: ObservePredictRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await observe_predict(self._primitive_client, payload, headers=headers)

    async def intervene_do(
        self,
        payload: InterveneDoRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await intervene_do(self._primitive_client, payload, headers=headers)

    async def graph_neighbors(
        self,
        payload: GraphNeighborsRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await graph_neighbors(self._primitive_client, payload, headers=headers)

    async def graph_markov_blanket(
        self,
        payload: GraphMarkovBlanketRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await graph_markov_blanket(self._primitive_client, payload, headers=headers)

    async def graph_paths(
        self,
        payload: GraphPathsRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await graph_paths(self._primitive_client, payload, headers=headers)

    async def traverse_parents(
        self,
        payload: TraverseParentsRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await traverse_parents(self._primitive_client, payload, headers=headers)

    async def traverse_children(
        self,
        payload: TraverseChildrenRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await traverse_children(self._primitive_client, payload, headers=headers)

    async def validate_connectivity(
        self,
        payload: ExtensionsValidateConnectivityRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await validate_connectivity(self._primitive_client, payload, headers=headers)

    async def markov_blanket(
        self,
        payload: ExtensionsMarkovBlanketRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await markov_blanket(self._primitive_client, payload, headers=headers)

    async def counterfactual_preview(
        self,
        payload: ExtensionsCounterfactualPreviewRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await counterfactual_preview(self._primitive_client, payload, headers=headers)

    async def intervene_time_lag(
        self,
        payload: ExtensionsInterveneTimeLagRequest,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        return await intervene_time_lag(self._primitive_client, payload, headers=headers)
