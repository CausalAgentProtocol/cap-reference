from typing import cast

from fastapi import APIRouter, Request

from abel_cap_server.api.schemas.health import ServiceMetaResponse
from abel_cap_server.cap.catalog import CapabilityCard
from abel_cap_server.core.config import Settings
from abel_cap_server.cap.service import CapService

router = APIRouter(tags=["meta"])


@router.get("/", response_model=ServiceMetaResponse, summary="Service metadata")
def metadata(request: Request) -> ServiceMetaResponse:
    settings = cast(Settings, request.app.state.settings)
    return ServiceMetaResponse(
        name=settings.app_name,
        version=settings.app_version,
        docs="/docs",
        openapi="/openapi.json",
    )


@router.get(
    "/.well-known/cap.json",
    response_model=CapabilityCard,
    response_model_exclude_none=True,
    summary="CAP capability card",
)
def capability_card(request: Request) -> CapabilityCard:
    service = cast(CapService, request.app.state.cap_service)
    return service.build_capability_card(str(request.base_url))
