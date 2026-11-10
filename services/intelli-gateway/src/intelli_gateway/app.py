"""FastAPI application factory. Every route lives under /api and declares a response_model."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from intelli_gateway.api.middleware.request_id import request_id_middleware
from intelli_gateway.api.routers import (
    auth,
    forecast,
    health,
    knowledge,
    me,
    site_profiles,
    sites,
    tools,
    users,
)
from intelli_gateway.auth.bootstrap import ensure_configured_accounts
from intelli_gateway.config import Settings, load_settings
from intelli_gateway.services.postgres.database import migrate, wait_for_database
from intelli_gateway.utils.exceptions import (
    ConfigurationError,
    ConflictError,
    ForbiddenError,
    InvalidRequestError,
    LLMUnavailableError,
    NotFoundError,
    UnauthorizedError,
    UpstreamUnavailableError,
)
from intelli_gateway.utils.logger import configure_logging
from intelli_gateway.wiring import Services, build_services

# The OpenAPI `info.version` is this service's contract version: bump it for a breaking change
# (see contracts/README.md).
API_VERSION = "0.4.0"
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
    """Without `services` they are built at startup (lifespan) from the settings, so importing
    the app or rendering its contract needs no database or backend-ot; a missing DATABASE_URL
    fails the startup. Tests pass their own services (built from tests/doubles/)."""
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        services: Services = app.state.services or build_services(settings)
        app.state.services = services
        if services.database is not None:
            await wait_for_database(services.database)
            await migrate(services.database)
        await ensure_configured_accounts(services.auth, settings)
        services.forecast_job.start()
        services.site_profile_job.start()
        try:
            yield
        finally:
            await services.aclose()

    app = FastAPI(
        title="intelli-gateway", description=DESCRIPTION, version=API_VERSION, lifespan=lifespan
    )
    app.state.services = services
    app.state.settings = settings
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(NotFoundError, _error(404))
    app.add_exception_handler(UnauthorizedError, _error(401))
    app.add_exception_handler(ConflictError, _error(409))
    app.add_exception_handler(ForbiddenError, _error(403))
    app.add_exception_handler(InvalidRequestError, _error(422))
    app.add_exception_handler(LLMUnavailableError, _error(503))
    app.add_exception_handler(UpstreamUnavailableError, _error(503))
    app.add_exception_handler(ConfigurationError, _error(503))
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(me.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(sites.router, prefix="/api")
    app.include_router(site_profiles.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    app.include_router(tools.router, prefix="/api")
    app.include_router(forecast.router, prefix="/api")
    return app


app = create_app()
