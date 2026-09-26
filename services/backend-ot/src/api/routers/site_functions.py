"""
Site function endpoints: site-specific historian calculations.

One route is generated per SiteEndpoint declared in a site's profile.py (collected by
site_profiles/profile_registry.py), each with its own method, query-parameter and response
model, so every endpoint is fully typed in the OpenAPI contract. The endpoint's kind
decides the URL: common-* and site-* are site-wide, device-* take a device_id. A request
is served only if the site's own profile declares the endpoint.
"""

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, NoReturn

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from api.controllers.site_functions import list_site_endpoints, run_site_endpoint
from logger import get_logger
from schemas.site_profiles import SiteEndpointsResponse, TimeWindowParams
from site_profiles.profile_registry import SITE_ENDPOINT_ROUTES, SiteEndpointRoute
from utils.exceptions import AppError

router = APIRouter(prefix="/site-functions", tags=["site-functions"])
logger = get_logger(__name__)


def _function_error(e: Exception) -> NoReturn:
    """Map an exception to an HTTPException. Never returns."""
    if isinstance(e, AppError):
        detail = {"error": type(e).__name__, "message": e.message}
        if e.payload:
            detail.update(e.payload)
        raise HTTPException(status_code=e.http_status_code, detail=detail) from e
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal server error occurred",
    ) from e


@router.get(
    "/site/{site_id}",
    response_model=SiteEndpointsResponse,
    summary="List the endpoints a site's profile declares",
)
async def get_site_endpoints(site_id: int) -> SiteEndpointsResponse:
    try:
        return await list_site_endpoints(site_id)
    except Exception as e:
        _function_error(e)


def _build_endpoint(route: SiteEndpointRoute) -> Callable[..., Awaitable[BaseModel]]:
    """The FastAPI handler for one site endpoint, with a signature FastAPI reads to build its params."""

    async def endpoint(
        site_id: int, params: TimeWindowParams, device_id: int | None = None
    ) -> BaseModel:
        try:
            return await run_site_endpoint(site_id, route.name, params, device_id=device_id)
        except Exception as e:
            _function_error(e)

    path_params = [inspect.Parameter("site_id", inspect.Parameter.KEYWORD_ONLY, annotation=int)]
    if route.kind == "device":
        path_params.append(
            inspect.Parameter("device_id", inspect.Parameter.KEYWORD_ONLY, annotation=int)
        )
    endpoint.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            *path_params,
            inspect.Parameter(
                "params",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=Annotated[route.params_model, Query()],
            ),
        ]
    )
    return endpoint


for _route in SITE_ENDPOINT_ROUTES:
    _path = (
        f"/site/{{site_id}}/device/{{device_id}}/{_route.name}"
        if _route.kind == "device"
        else f"/site/{{site_id}}/{_route.name}"
    )
    router.add_api_route(
        _path,
        _build_endpoint(_route),
        methods=[_route.method],
        response_model=_route.response_model,
        summary=_route.summary,
        name=f"site_function_{_route.name.replace('-', '_')}",
    )
