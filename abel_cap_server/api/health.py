from typing import cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from abel_cap_server.core.config import Settings


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    version: str


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check(request: Request) -> HealthResponse:
    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )
