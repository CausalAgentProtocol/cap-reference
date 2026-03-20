from fastapi import APIRouter

from abel_cap_server.api import cap_dispatch, health, meta

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(cap_dispatch.router)
api_router.include_router(health.router)
