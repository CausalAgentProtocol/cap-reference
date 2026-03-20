from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from abel_cap_server.cap.catalog import build_dispatch_registry
from abel_cap_server.cap.provenance import get_abel_provenance_context
from cap.server import build_fastapi_cap_dispatcher


DISPATCH_REGISTRY = build_dispatch_registry()
CAP_DISPATCHER = build_fastapi_cap_dispatcher(
    registry=DISPATCH_REGISTRY,
    provenance_context_provider=get_abel_provenance_context,
)

router = APIRouter(tags=["cap"])


@router.post("/cap", summary="Dispatch CAP verbs by payload.verb")
async def dispatch_cap(
    payload: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    return await CAP_DISPATCHER(payload, request)
