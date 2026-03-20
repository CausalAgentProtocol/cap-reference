from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from abel_cap_server.cap.contracts import (
    ExtensionsInterveneTimeLagResponse,
    ExtensionsMarkovBlanketResponse,
)
from cap.client import AsyncCAPClient, CAPClientRoutes
from cap.core.envelopes import CAPRequestOptions

ABEL_MARKOV_BLANKET_ROUTE = "extensions/abel/markov_blanket"
ABEL_INTERVENE_TIME_LAG_ROUTE = "extensions/abel/intervene_time_lag"
DEFAULT_CAP_ROUTES = CAPClientRoutes(single_entry_path="/cap")


class AsyncAbelCAPClient(AsyncCAPClient):
    def __init__(self, base_url: str, **kwargs: Any) -> None:
        kwargs.setdefault("routes", DEFAULT_CAP_ROUTES)
        super().__init__(base_url, **kwargs)

    async def markov_blanket(
        self,
        *,
        target_node: str,
        model: str = "linear",
        feature_type: str = "MB",
        request_id: str | None = None,
        options: CAPRequestOptions | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ExtensionsMarkovBlanketResponse:
        return await self.request_route(
            ABEL_MARKOV_BLANKET_ROUTE,
            params={
                "target_node": target_node,
                "model": model,
                "feature_type": feature_type,
            },
            request_id=request_id,
            options=options,
            headers=headers,
            response_model=ExtensionsMarkovBlanketResponse,
        )

    async def intervene_time_lag(
        self,
        *,
        treatment_node: str,
        treatment_value: float,
        outcome_node: str,
        horizon_steps: int,
        model: str = "linear",
        request_id: str | None = None,
        options: CAPRequestOptions | None = None,
        extra_params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ExtensionsInterveneTimeLagResponse:
        params: dict[str, Any] = {
            "treatment_node": treatment_node,
            "treatment_value": treatment_value,
            "outcome_node": outcome_node,
            "horizon_steps": horizon_steps,
            "model": model,
        }
        if extra_params is not None:
            params.update(dict(extra_params))
        return await self.request_route(
            ABEL_INTERVENE_TIME_LAG_ROUTE,
            params=params,
            request_id=request_id,
            options=options,
            headers=headers,
            response_model=ExtensionsInterveneTimeLagResponse,
        )


__all__ = [
    "ABEL_INTERVENE_TIME_LAG_ROUTE",
    "ABEL_MARKOV_BLANKET_ROUTE",
    "DEFAULT_CAP_ROUTES",
    "AsyncAbelCAPClient",
]
