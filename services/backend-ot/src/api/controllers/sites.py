"""
Sites controller.

Sits between the router and the DB/helper layers.
No cache layer — all reads and writes go directly to the DB.
"""

from typing import Literal

import db.sites as sites_db
from helpers.alarms.profile_sync import sync_site_profile_alarms
from helpers.sites import get_complete_site_data_with_points
from logger import get_logger
from schemas.api_models import (
    SiteComprehensiveResponse,
    SiteCreateRequest,
    SiteResponse,
    SiteUpdateRequest,
)
from schemas.site_profiles import SiteSld
from site_profiles.common.profile import DEFAULT_PROFILE_KEY
from site_profiles.profile_registry import get_site_profile, validate_profile_key
from utils.exceptions import NotFoundError

logger = get_logger(__name__)


async def get_all_sites(include_deleted: bool = False) -> list[SiteResponse]:
    return await sites_db.get_all_sites(include_deleted=include_deleted)


async def get_site_by_id(site_id: int, include_deleted: bool = False) -> SiteResponse | None:
    return await sites_db.get_site_by_id(site_id, include_deleted=include_deleted)


async def create_site(site: SiteCreateRequest) -> SiteResponse:
    if site.profile is None:
        site = site.model_copy(update={"profile": DEFAULT_PROFILE_KEY})
    validate_profile_key(site.profile)
    created = await sites_db.create_site(site)
    # The site gets an alarm row per alarm its profile declares in code.
    await sync_site_profile_alarms(created.site_id)
    return created


async def update_site(site_id: int, site_update: SiteUpdateRequest) -> SiteResponse:
    validate_profile_key(site_update.profile)
    updated = await sites_db.update_site(site_id, site_update)
    if site_update.profile is not None:
        await sync_site_profile_alarms(site_id)
    return updated


async def delete_site(
    site_id: int,
    mode: Literal["soft", "hard"] = "soft",
    confirm: bool = False,
) -> SiteResponse | None:
    return await sites_db.delete_site(site_id, mode=mode, confirm=confirm)


async def restore_site(site_id: int) -> SiteResponse | None:
    return await sites_db.restore_site(site_id)


async def get_comprehensive_site(site_id: int) -> SiteComprehensiveResponse | None:
    return await get_complete_site_data_with_points(site_id)


async def get_site_sld(site_id: int) -> SiteSld:
    """The single line diagram of the site's profile (404 if the site or its diagram is missing)."""
    site = await sites_db.get_site_by_id(site_id)
    if site is None:
        raise NotFoundError(f"Site with id {site_id} not found")
    sld = get_site_profile(site.profile).sld
    if sld is None:
        raise NotFoundError(
            f"Site {site_id}'s profile '{site.profile}' has no single line diagram",
            payload={"profile": site.profile},
        )
    return sld
