from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from abel_cap_server.cap import handlers
from abel_cap_server.cap.contracts import (
    AbelGraphPathsResponse,
    ExtensionsCounterfactualPreviewRequest,
    ExtensionsCounterfactualPreviewResponse,
    ExtensionsInterveneTimeLagRequest,
    ExtensionsInterveneTimeLagResponse,
    ExtensionsMarkovBlanketRequest,
    ExtensionsMarkovBlanketResponse,
    ExtensionsValidateConnectivityRequest,
    ExtensionsValidateConnectivityResponse,
)
from abel_cap_server.cap.disclosure import DEFAULT_ASSUMPTIONS, FORBIDDEN_FIELDS
from abel_cap_server.core.config import Settings
from cap.core.contracts import GraphPathsRequest
from cap.core import (
    CAPABILITY_CARD_SCHEMA_URL,
    CapabilityAccessTier,
    CapabilityAuthentication,
    CapabilityCard,
    CapabilityCausalEngine,
    CapabilityDetailedCapabilities,
    CapabilityDisclosurePolicy,
    CapabilityExtensionNamespace,
    CapabilityGraphMetadata,
    CapabilityProvider,
    CapabilityStructuralMechanisms,
    CapabilitySupportedVerbs,
    REASONING_MODE_GRAPH_PROPAGATION,
    REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
    REASONING_MODE_OBSERVATIONAL_PREDICTION,
    REASONING_MODE_STRUCTURAL_SEMANTICS,
    REASONING_MODE_VALIDATION_GATE,
)
from cap.core.constants import CAP_VERSION
from cap.server import (
    CAPVerbRegistry,
    GRAPH_MARKOV_BLANKET_CONTRACT,
    GRAPH_NEIGHBORS_CONTRACT,
    INTERVENE_DO_CONTRACT,
    META_CAPABILITIES_CONTRACT,
    OBSERVE_PREDICT_CONTRACT,
    TRAVERSE_CHILDREN_CONTRACT,
    TRAVERSE_PARENTS_CONTRACT,
)


@dataclass(frozen=True)
class CAPServerIdentity:
    server_name: str
    server_version: str


@dataclass(frozen=True)
class CAPGraphProfile:
    graph_id: str
    graph_version: str
    domains: tuple[str, ...]
    node_count: int
    edge_count: int
    node_types: tuple[str, ...]
    edge_types_supported: tuple[str, ...]
    graph_representation: str
    update_frequency: str
    temporal_resolution: str
    coverage_description: str


DEFAULT_CAP_GRAPH_PROFILE = CAPGraphProfile(
    graph_id="abel-main",
    graph_version="CausalNodeV2",
    domains=("equities", "crypto"),
    node_count=11315,
    edge_count=42105965,
    node_types=("close_price", "volume"),
    edge_types_supported=("directed_lagged",),
    graph_representation="time_lagged_dag",
    update_frequency="PT24H",
    temporal_resolution="PT1H",
    coverage_description=(
        "Adapter over Abel Graph Computer primitive endpoints backed by the live CausalNodeV2 graph. "
        "Exact weights, taus, conditioning sets, p-values, and CI internals stay hidden by default."
    ),
)

ABEL_EXTENSION_ADDITIONAL_PARAMS = {
    "graph.paths": {
        "include_edge_signs": "boolean",
    }
}

DEFAULT_DISCLOSURE_NOTES = [
    "Primitive hidden-field policy is inherited by default.",
    "intervene.do uses the server's default linear SCM rollout over the public time-lagged graph.",
    "validate is exposed only as an Abel extension.",
]

ABEL_EXTENSION_NOTES = [
    "Abel owns the abel extension namespace.",
    "validate_connectivity uses an undirected shortest-path connectivity proxy rather than strict d-separation or IV identification.",
    "counterfactual_preview remains a preview interface and does not claim Level 3 CAP conformance.",
    "counterfactual_preview uses approximate graph propagation rather than full abduction-action-prediction semantics.",
]


def server_identity_from_settings(settings: Settings) -> CAPServerIdentity:
    return CAPServerIdentity(
        server_name=settings.app_name,
        server_version=settings.app_version,
    )


# The protocol registry supports decorator-style registration, but this app keeps
# CAP surface wiring centralized here so developers can review public verbs,
# extensions, and capability-card metadata in one place.
DISPATCH_REGISTRY = CAPVerbRegistry()
DISPATCH_REGISTRY.core(META_CAPABILITIES_CONTRACT)(handlers.meta_capabilities)


def _register_service_handlers() -> None:
    DISPATCH_REGISTRY.core(OBSERVE_PREDICT_CONTRACT)(handlers.observe_predict)
    DISPATCH_REGISTRY.core(INTERVENE_DO_CONTRACT)(handlers.intervene_do)
    DISPATCH_REGISTRY.core(GRAPH_NEIGHBORS_CONTRACT)(handlers.graph_neighbors)
    DISPATCH_REGISTRY.core(GRAPH_MARKOV_BLANKET_CONTRACT)(handlers.graph_markov_blanket)
    DISPATCH_REGISTRY.core(
        "graph.paths",
        request_model=GraphPathsRequest,
        response_model=AbelGraphPathsResponse,
    )(handlers.graph_paths)
    DISPATCH_REGISTRY.core(TRAVERSE_PARENTS_CONTRACT, surface="convenience")(
        handlers.traverse_parents
    )
    DISPATCH_REGISTRY.core(TRAVERSE_CHILDREN_CONTRACT, surface="convenience")(
        handlers.traverse_children
    )
    DISPATCH_REGISTRY.extension(
        namespace="abel",
        name="validate_connectivity",
        request_model=ExtensionsValidateConnectivityRequest,
        response_model=ExtensionsValidateConnectivityResponse,
    )(handlers.validate_connectivity)
    DISPATCH_REGISTRY.extension(
        namespace="abel",
        name="markov_blanket",
        request_model=ExtensionsMarkovBlanketRequest,
        response_model=ExtensionsMarkovBlanketResponse,
    )(handlers.markov_blanket)
    DISPATCH_REGISTRY.extension(
        namespace="abel",
        name="counterfactual_preview",
        request_model=ExtensionsCounterfactualPreviewRequest,
        response_model=ExtensionsCounterfactualPreviewResponse,
    )(handlers.counterfactual_preview)
    DISPATCH_REGISTRY.extension(
        namespace="abel",
        name="intervene_time_lag",
        request_model=ExtensionsInterveneTimeLagRequest,
        response_model=ExtensionsInterveneTimeLagResponse,
    )(handlers.intervene_time_lag)


def build_dispatch_registry() -> CAPVerbRegistry:
    return DISPATCH_REGISTRY


def build_supported_verbs(registry: CAPVerbRegistry | None = None) -> CapabilitySupportedVerbs:
    active_registry = registry or DISPATCH_REGISTRY
    return CapabilitySupportedVerbs(
        core=active_registry.verbs_for_surface("core"),
        convenience=active_registry.verbs_for_surface("convenience"),
    )


def _build_abel_extension_namespace(verbs: Sequence[str]) -> CapabilityExtensionNamespace:
    return CapabilityExtensionNamespace(
        schema_url="https://abel.ai/cap/extensions/abel/v1.json",
        verbs=list(verbs),
        additional_params=ABEL_EXTENSION_ADDITIONAL_PARAMS,
        notes=ABEL_EXTENSION_NOTES,
    )


def build_extension_namespaces(
    registry: CAPVerbRegistry | None = None,
) -> dict[str, CapabilityExtensionNamespace]:
    active_registry = registry or DISPATCH_REGISTRY
    return {
        namespace: _build_abel_extension_namespace(verbs)
        for namespace, verbs in active_registry.extension_verbs_by_namespace.items()
        if namespace == "abel"
    }


def build_capability_card(settings: Settings, *, public_base_url: str) -> CapabilityCard:
    endpoint = f"{public_base_url.rstrip('/')}/cap"
    supported_verbs = build_supported_verbs(DISPATCH_REGISTRY)
    extension_verbs = [
        verb for verbs in DISPATCH_REGISTRY.extension_verbs_by_namespace.values() for verb in verbs
    ]
    return CapabilityCard(
        schema_url=CAPABILITY_CARD_SCHEMA_URL,
        name="Abel CAP Primitive Adapter",
        description=(
            f"CAP {CAP_VERSION} adapter over Abel Graph Computer primitives. "
            "This service treats the primitive layer as the execution substrate, preserves its hidden-field policy by default, "
            "and exposes intervention results using the server's default linear SCM rollout over the public time-lagged graph."
        ),
        version=settings.app_version,
        cap_spec_version=CAP_VERSION,
        provider=CapabilityProvider(
            name=settings.cap_provider_name,
            url=settings.cap_provider_url,
        ),
        endpoint=endpoint,
        conformance_level=2,
        supported_verbs=supported_verbs,
        causal_engine=CapabilityCausalEngine(
            family="abel_primitive_adapter",
            algorithm="abel_graph_primitives",
            supports_time_lag=True,
            supports_instantaneous=False,
            structural_mechanisms=CapabilityStructuralMechanisms(
                available=True,
                families=["linear_scm"],
                mechanism_override_supported=False,
                counterfactual_ready=False,
            ),
        ),
        detailed_capabilities=CapabilityDetailedCapabilities(
            graph_discovery=False,
            graph_traversal=True,
            temporal_multi_lag=True,
            effect_estimation=True,
            intervention_simulation=True,
            counterfactual_scm=False,
            latent_confounding_modeled=False,
            partial_identification=False,
            uncertainty_quantified=False,
        ),
        assumptions=DEFAULT_ASSUMPTIONS,
        reasoning_modes_supported=[
            REASONING_MODE_OBSERVATIONAL_PREDICTION,
            REASONING_MODE_IDENTIFIED_CAUSAL_EFFECT,
            REASONING_MODE_GRAPH_PROPAGATION,
            REASONING_MODE_STRUCTURAL_SEMANTICS,
            REASONING_MODE_VALIDATION_GATE,
        ],
        graph=CapabilityGraphMetadata(
            domains=list(DEFAULT_CAP_GRAPH_PROFILE.domains),
            node_count=DEFAULT_CAP_GRAPH_PROFILE.node_count,
            edge_count=DEFAULT_CAP_GRAPH_PROFILE.edge_count,
            node_types=list(DEFAULT_CAP_GRAPH_PROFILE.node_types),
            edge_types_supported=list(DEFAULT_CAP_GRAPH_PROFILE.edge_types_supported),
            graph_representation=DEFAULT_CAP_GRAPH_PROFILE.graph_representation,
            update_frequency=DEFAULT_CAP_GRAPH_PROFILE.update_frequency,
            temporal_resolution=DEFAULT_CAP_GRAPH_PROFILE.temporal_resolution,
            coverage_description=DEFAULT_CAP_GRAPH_PROFILE.coverage_description,
        ),
        authentication=CapabilityAuthentication(type="none"),
        access_tiers=[
            CapabilityAccessTier(
                tier="public",
                verbs=supported_verbs.core + supported_verbs.convenience + extension_verbs,
                response_detail="summary",
                hidden_fields=list(FORBIDDEN_FIELDS),
            )
        ],
        disclosure_policy=CapabilityDisclosurePolicy(
            hidden_fields=list(FORBIDDEN_FIELDS),
            default_response_detail="summary",
            notes=DEFAULT_DISCLOSURE_NOTES,
        ),
        extensions=build_extension_namespaces(DISPATCH_REGISTRY),
    )


_register_service_handlers()


__all__ = [
    "CAPGraphProfile",
    "CAPServerIdentity",
    "CapabilityAccessTier",
    "CapabilityAuthentication",
    "CapabilityCard",
    "CapabilityDisclosurePolicy",
    "CapabilityExtensionNamespace",
    "CapabilityGraphMetadata",
    "CapabilityProvider",
    "CapabilitySupportedVerbs",
    "DEFAULT_CAP_GRAPH_PROFILE",
    "DISPATCH_REGISTRY",
    "build_capability_card",
    "build_dispatch_registry",
    "build_extension_namespaces",
    "build_supported_verbs",
    "server_identity_from_settings",
]
