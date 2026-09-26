"""
The standard shape of a site endpoint, and of a site's profile.

A site's functions.py may hold any number of functions. Only the ones declared as a
SiteEndpoint in that site's profile.py get a URL. Every declaration has the same fields:

    SiteEndpoint(
        method="GET",
        kind="site",                         # common | site | device
        name="site-poi-power",               # last URL segment, starts with '<kind>-'
        controller=site_poi_power,           # async (ctx, params) -> response_model
        response_model=PoiPowerResult,
        summary="POI active power series with peak and average (kW)",
    )

URL by kind:
    common, site   GET /api/site-functions/site/{site_id}/<name>
    device         GET /api/site-functions/site/{site_id}/device/{device_id}/<name>

SiteContext (defined in schemas.site_profiles, re-exported here) is the site, its devices
and their points, loaded once per request and passed to the controller.
"""

import inspect
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.site_profiles import FunctionKind, SiteContext, TimeWindowParams

__all__ = ["SiteContext", "SiteController", "SiteEndpoint", "SiteProfile"]

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

    @field_validator("controller")
    @classmethod
    def _controller_is_async(cls, controller: SiteController) -> SiteController:
        if not inspect.iscoroutinefunction(controller):
            raise ValueError(f"controller {controller!r} must be an 'async def' function")
        return controller


class SiteProfile(BaseModel):
    """The endpoints one site offers. Its key is the value stored in sites.profile."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(..., min_length=1, max_length=64, description="Stored in sites.profile, e.g. 'alpha_solar'")
    endpoints: tuple[SiteEndpoint, ...]

    def find_endpoint(self, name: str) -> SiteEndpoint | None:
        """The declared endpoint with this name, or None if the site doesn't offer it."""
        return next((endpoint for endpoint in self.endpoints if endpoint.name == name), None)
