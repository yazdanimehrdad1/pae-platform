"""
Site functions controller.

Resolves a request to the right code: site exists → site's profile → device (for
device endpoints) → the endpoint the profile declares under that name → await its
controller with a SiteContext.
"""

from pydantic import BaseModel

import db.devices as devices_db
import db.sites as sites_db
from schemas.api_models import SiteResponse
from schemas.site_profiles import (
    SiteContext,
    SiteEndpointInfo,
    SiteEndpointsResponse,
    TimeWindowParams,
)
from site_profiles.profile_registry import get_site_profile
from utils.exceptions import NotFoundError


async def _get_site(site_id: int) -> SiteResponse:
    site = await sites_db.get_site_by_id(site_id)
    if site is None:
        raise NotFoundError(f"Site with id {site_id} not found")
    return site


async def list_site_endpoints(site_id: int) -> SiteEndpointsResponse:
    site = await _get_site(site_id)
    profile = get_site_profile(site.profile)
    return SiteEndpointsResponse(
        site_id=site_id,
        profile=profile.key,
        endpoints=[
            SiteEndpointInfo(
                name=endpoint.name, kind=endpoint.kind, method=endpoint.method, summary=endpoint.summary
            )
            for endpoint in profile.endpoints
        ],
    )


async def run_site_endpoint(
    site_id: int,
    endpoint_name: str,
    params: TimeWindowParams,
    device_id: int | None = None,
) -> BaseModel:
    site = await _get_site(site_id)
    profile = get_site_profile(site.profile)

    devices = await devices_db.get_all_devices(site_id)
    device = None
    if device_id is not None:
        device = next((site_device for site_device in devices if site_device.device_id == device_id), None)
        if device is None:
            raise NotFoundError(f"Device with ID {device_id} not found in site {site_id}")

    endpoint = profile.find_endpoint(endpoint_name)
    if endpoint is None:
        raise NotFoundError(
            f"Endpoint '{endpoint_name}' is not declared for site {site_id} (profile '{profile.key}')"
        )

    ctx = SiteContext(site=site, devices=devices, device=device)
    return await endpoint.controller(ctx, params)
