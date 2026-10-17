"""FastAPI application factory. Every route lives under /api and declares a response_model."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from intelli_gateway.api.middleware.request_id import request_id_middleware
from intelli_gateway.api.routers import health, sites, tools
from intelli_gateway.config import Settings, load_settings
from intelli_gateway.utils.exceptions import ForbiddenError, LLMUnavailableError, NotFoundError
from intelli_gateway.utils.logger import configure_logging
from intelli_gateway.wiring import Services, build_services

# The OpenAPI `info.version` is this service's contract version: bump it for a breaking change
# (see contracts/README.md).
API_VERSION = "0.1.0"
DESCRIPTION = (
    "AI helper for site engineers: Claude answers questions about a generation site using "
    "read-only tools"
)


def _error(status_code: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, error: Exception) -> JSONResponse:
        del request
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handler


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or load_settings()
    services = services or build_services(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        configure_logging(settings.log_level)
        yield
        await services.aclose()

    app = FastAPI(
        title="intelli-gateway", description=DESCRIPTION, version=API_VERSION, lifespan=lifespan
    )
    app.state.services = services
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(NotFoundError, _error(404))
    app.add_exception_handler(ForbiddenError, _error(403))
    app.add_exception_handler(LLMUnavailableError, _error(503))
    app.include_router(health.router, prefix="/api")
    app.include_router(sites.router, prefix="/api")
    app.include_router(tools.router, prefix="/api")
    return app


app = create_app()
