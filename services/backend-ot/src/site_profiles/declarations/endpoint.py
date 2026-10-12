"""
The standard shape of a site endpoint.

A site's functions.py may hold any number of functions. Only the ones declared as a
SiteEndpoint in that site's profile.py get a URL. Every declaration has the same fields:

    SiteEndpoint(
        method="GET",
        kind="site",                         # common | site | device
        name="site-poi-power",               # last URL segment, starts with '<kind>-'
        controller=site_poi_power,           # async (ctx, params) -> response_model
        response_model=PoiPowerResult,
        summary="POI active power series with peak and average (kW)",
        output="series",                     # scalar (default) | series
    )

output="series" marks an endpoint whose response has a `series` field (one PointTimeseries or a
list of them); the historian lists those next to device points. A series keeps its points' own
sample times, never a resampled grid (see common/shared_helper_functions.py for how to derive
and combine series), so it lines up with the raw points it is charted with. A device endpoint may also name
the device_types it applies to (empty: every device), so a UI offers it only under those devices.

URL by kind:
    common, site   GET /api/site-functions/site/{site_id}/<name>
    device         GET /api/site-functions/site/{site_id}/device/{device_id}/<name>

SiteContext (defined in schemas.site_profiles, re-exported here) is the site, its devices
and their points, loaded once per request and passed to the controller.
"""

import inspect
from collections.abc import Awaitable, Callable
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.api_models.types import DeviceType
from schemas.site_profiles import EndpointOutput, FunctionKind, SiteContext, TimeWindowParams

__all__ = ["SiteContext", "SiteController", "SiteEndpoint"]

SiteController = Callable[[SiteContext, TimeWindowParams], Awaitable[BaseModel]]
"""The standard controller signature: async def <name>(ctx, params) -> <response_model>."""


class SiteEndpoint(BaseModel):
    """One endpoint a site offers. Declared in site_profiles/individual_sites/<site>/profile.py."""

    model_config = ConfigDict(frozen=True)

    method: Literal["GET"] = Field(..., description="HTTP method; only GET for now")
    kind: FunctionKind = Field(
        ..., description="common: shared by all sites; site: this site, site-wide; device: this site, one device"
    )
    name: str = Field(..., description="Last URL segment: '<kind>-' plus lower-case words joined by '-'")
    controller: SiteController = Field(..., description="The async function that serves the endpoint")
    params_model: type[TimeWindowParams] = Field(
        TimeWindowParams, description="Query parameters; TimeWindowParams or a subclass of it"
    )
    response_model: type[BaseModel] = Field(..., description="Response body; must be the controller's return type")
    summary: str = Field(..., min_length=1, description="One line for OpenAPI and the discovery endpoint")
    output: EndpointOutput = Field(
        "scalar", description="series: the response has a `series` field (PointTimeseries or a list of them)"
    )
    device_types: tuple[DeviceType, ...] = Field(
        (), description="Device endpoints only: the device types it applies to; empty means every device"
    )

    @field_validator("controller")
    @classmethod
    def _controller_is_async(cls, controller: SiteController) -> SiteController:
        if not inspect.iscoroutinefunction(controller):
            raise ValueError(f"controller {controller!r} must be an 'async def' function")
        return controller

    @model_validator(mode="after")
    def _device_types_only_on_device_kind(self) -> Self:
        if self.device_types and self.kind != "device":
            raise ValueError(f"device_types is only for device endpoints, not kind '{self.kind}'")
        return self
