from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from cap.core.contracts import (
    CAPProvenancedSuccessResponse,
    SemanticHonestyFields,
)
from cap.core.envelopes import CAPRequestBase


class CAPValidatePairResult(BaseModel):
    node_a: str
    node_b: str
    connected: bool


class CAPValidateInvalidVariable(BaseModel):
    node: str
    reason: str


class ExtensionsValidateConnectivityParams(BaseModel):
    variables: list[str] = Field(min_length=2, max_length=12)


class ExtensionsValidateConnectivityRequest(CAPRequestBase):
    verb: Literal["extensions.abel.validate_connectivity"] = "extensions.abel.validate_connectivity"
    params: ExtensionsValidateConnectivityParams


class ExtensionsValidateConnectivityResult(SemanticHonestyFields):
    validation_method: str
    proxy_only: bool = True
    connectivity_semantics: Literal["undirected_shortest_path_proxy"] = (
        "undirected_shortest_path_proxy"
    )
    passed: bool
    valid_variables: list[str] = Field(default_factory=list)
    invalid_variables: list[CAPValidateInvalidVariable] = Field(default_factory=list)
    pair_results: list[CAPValidatePairResult] = Field(default_factory=list)


class ExtensionsValidateConnectivityResponse(
    CAPProvenancedSuccessResponse[ExtensionsValidateConnectivityResult]
):
    verb: Literal["extensions.abel.validate_connectivity"] = "extensions.abel.validate_connectivity"


class ExtensionsMarkovBlanketParams(BaseModel):
    target_node: str = Field(min_length=1)


class ExtensionsMarkovBlanketRequest(CAPRequestBase):
    verb: Literal["extensions.abel.markov_blanket"] = "extensions.abel.markov_blanket"
    params: ExtensionsMarkovBlanketParams


class ExtensionsMarkovBlanketResult(SemanticHonestyFields):
    target_node: str
    drivers: list[str] = Field(default_factory=list)
    markov_blanket: list[str] = Field(default_factory=list)


class ExtensionsMarkovBlanketResponse(CAPProvenancedSuccessResponse[ExtensionsMarkovBlanketResult]):
    verb: Literal["extensions.abel.markov_blanket"] = "extensions.abel.markov_blanket"


class ExtensionsCounterfactualPreviewParams(BaseModel):
    intervene_node: str = Field(min_length=1)
    intervene_time: str = Field(min_length=1)
    observe_node: str = Field(min_length=1)
    observe_time: str = Field(min_length=1)
    intervene_new_value: float


class ExtensionsCounterfactualPreviewRequest(CAPRequestBase):
    verb: Literal["extensions.abel.counterfactual_preview"] = (
        "extensions.abel.counterfactual_preview"
    )
    params: ExtensionsCounterfactualPreviewParams


class CounterfactualObserveDelta(BaseModel):
    factual_value: float | None = None
    counterfactual_value: float | None = None
    change: float | None = None


class ExtensionsCounterfactualPreviewResult(SemanticHonestyFields):
    intervene_node: str
    observe_node: str
    intervene: dict[str, Any]
    observe: CounterfactualObserveDelta
    preview_only: bool = True
    counterfactual_semantics: Literal["approximate_graph_propagation"] = (
        "approximate_graph_propagation"
    )
    effect_support: Literal["reachable", "no_structural_path"]
    reachable: bool
    path_count: int


class ExtensionsCounterfactualPreviewResponse(
    CAPProvenancedSuccessResponse[ExtensionsCounterfactualPreviewResult]
):
    verb: Literal["extensions.abel.counterfactual_preview"] = (
        "extensions.abel.counterfactual_preview"
    )


class ExtensionsInterveneTimeLagParams(BaseModel):
    treatment_node: str = Field(min_length=1)
    treatment_value: float
    outcome_node: str = Field(min_length=1)
    horizon_steps: int = Field(ge=1, le=168)
    model: str = "linear"


class ExtensionsInterveneTimeLagRequest(CAPRequestBase):
    verb: Literal["extensions.abel.intervene_time_lag"] = "extensions.abel.intervene_time_lag"
    params: ExtensionsInterveneTimeLagParams


class TimeLagEffectSummary(BaseModel):
    node_id: str
    final_cumulative_effect: float
    first_arrive_step: int
    last_arrive_step: int
    event_count: int
    # Same semantics as the core intervention claim field: only set this when
    # the server can honestly certify full structural mechanism coverage.
    mechanism_coverage_complete: bool | None = None


class ExtensionsInterveneTimeLagResult(BaseModel):
    treatment_node: str
    treatment_value: float
    model: str
    delta_unit: str
    horizon_steps: int
    outcome_node: str
    reasoning_mode: str
    outcome_summary: TimeLagEffectSummary
    total_events: int
    identification_status: str
    assumptions: list[str] = Field(default_factory=list)


class ExtensionsInterveneTimeLagResponse(
    CAPProvenancedSuccessResponse[ExtensionsInterveneTimeLagResult]
):
    verb: Literal["extensions.abel.intervene_time_lag"] = "extensions.abel.intervene_time_lag"


__all__ = [
    "CAPValidateInvalidVariable",
    "CAPValidatePairResult",
    "CounterfactualObserveDelta",
    "ExtensionsCounterfactualPreviewParams",
    "ExtensionsCounterfactualPreviewRequest",
    "ExtensionsCounterfactualPreviewResponse",
    "ExtensionsCounterfactualPreviewResult",
    "ExtensionsInterveneTimeLagParams",
    "ExtensionsInterveneTimeLagRequest",
    "ExtensionsInterveneTimeLagResponse",
    "ExtensionsInterveneTimeLagResult",
    "ExtensionsMarkovBlanketParams",
    "ExtensionsMarkovBlanketRequest",
    "ExtensionsMarkovBlanketResponse",
    "ExtensionsMarkovBlanketResult",
    "ExtensionsValidateConnectivityParams",
    "ExtensionsValidateConnectivityRequest",
    "ExtensionsValidateConnectivityResponse",
    "ExtensionsValidateConnectivityResult",
    "TimeLagEffectSummary",
]
