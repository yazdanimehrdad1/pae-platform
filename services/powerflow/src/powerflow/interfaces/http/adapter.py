"""The HTTP adapter: FastAPI routers mounted under /api, and the error → status code mapping.

The routers are served by the app's own uvicorn server, so start()/stop() have nothing to do.
"""

import platform
from importlib.metadata import version

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from powerflow.errors import (
    ConditionError,
    InvalidNameError,
    InvalidStateError,
    NotFoundError,
    PointAccessError,
    PowerflowError,
    ProfileError,
    SetpointError,
    SiteConfigError,
    UnknownAssetError,
    UnknownPointError,
)
from powerflow.interfaces.base import AdapterContext, AdapterRegistry, ProtocolAdapter
from powerflow.interfaces.http import (
    routes_assets,
    routes_conditions,
    routes_config,
    routes_devices,
    routes_event_scenarios,
    routes_library,
    routes_measurements,
    routes_modbus,
    routes_sim,
)
from powerflow.interfaces.http.dependencies import get_adapters, get_context
from powerflow.interfaces.http.schemas import HealthResponse, VersionResponse

SERVICE_NAME = "powerflow"
STATUS_BY_ERROR: list[tuple[type[PowerflowError], int]] = [
    (UnknownAssetError, 404),
    (UnknownPointError, 404),
    (NotFoundError, 404),
    (InvalidNameError, 422),
    (InvalidStateError, 409),
    (SetpointError, 422),
    (ProfileError, 422),
    (SiteConfigError, 422),
    (ConditionError, 422),
    (PointAccessError, 422),
]


class HttpAdapter(ProtocolAdapter):
    name = "http"

    async def start(self) -> None:
        """Nothing to start: uvicorn serves the routers."""

    async def stop(self) -> None:
        """Nothing to stop."""


def build_router(api_version: str) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, tags=["health"], summary="Liveness")
    async def health(
        context: AdapterContext = Depends(get_context),
        adapters: AdapterRegistry = Depends(get_adapters),
    ) -> HealthResponse:
        return HealthResponse(
            ok=True,
            state=context.engine.run_state,
            interfaces=adapters.running,
            interface_errors=adapters.failed,
        )

    @router.get("/version", response_model=VersionResponse, tags=["health"], summary="Versions")
    async def get_version() -> VersionResponse:
        return VersionResponse(
            service=SERVICE_NAME,
            api_version=api_version,
            pandapower_version=version("pandapower"),
            python_version=platform.python_version(),
        )

    router.include_router(routes_sim.router)
    router.include_router(routes_conditions.router)
    router.include_router(routes_config.router)
    router.include_router(routes_library.router)
    router.include_router(routes_event_scenarios.router)
    router.include_router(routes_assets.router)
    router.include_router(routes_measurements.router)
    router.include_router(routes_devices.router)
    router.include_router(routes_modbus.router)
    return router


def install_error_handlers(app: FastAPI) -> None:
    async def handle(request: Request, error: Exception) -> JSONResponse:
        status_code = next(
            (code for error_type, code in STATUS_BY_ERROR if isinstance(error, error_type)), 500
        )
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    for error_type, _ in STATUS_BY_ERROR:
        app.add_exception_handler(error_type, handle)
