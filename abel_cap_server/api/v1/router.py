from fastapi import APIRouter

from abel_cap_server.api.v1.endpoints import cap_dispatch, health

api_router = APIRouter()
api_router.include_router(cap_dispatch.router)
api_router.include_router(health.router)
