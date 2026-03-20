from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from abel_cap_server.api.meta import router as meta_router
from abel_cap_server.api.v1.router import api_router
from abel_cap_server.cap.errors import register_cap_exception_handlers
from abel_cap_server.clients.abel_gateway_client import AbelGatewayClient
from abel_cap_server.cap.service import CapService
from abel_cap_server.core.config import Settings, get_settings
from abel_cap_server.core.logging import configure_logging
from abel_cap_server.middlewares.request_logging import RequestLoggingMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(log_level=active_settings.log_level, json_logs=active_settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "runtime_configuration",
            extra={
                "app_env": active_settings.app_env,
                "app_host": active_settings.app_host,
                "app_port": active_settings.app_port,
                "api_v1_prefix": active_settings.api_v1_prefix,
                "upstream_configured": bool(active_settings.cap_upstream_base_url),
            },
        )
        try:
            yield
        finally:
            primitive_client = getattr(app.state, "abel_primitive_client", None)
            if primitive_client is not None:
                await primitive_client.aclose()

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.state.settings = active_settings
    app.state.abel_primitive_client = AbelGatewayClient(settings=active_settings)
    app.state.cap_service = CapService(
        settings=active_settings,
        primitive_client=app.state.abel_primitive_client,
    )

    register_cap_exception_handlers(app)
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(meta_router)
    app.include_router(api_router, prefix=active_settings.api_v1_prefix)
    return app


app = create_app()


def main():
    import uvicorn

    config = get_settings()
    uvicorn.run(
        "abel_cap_server.main:app",
        host=config.app_host,
        port=config.app_port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
