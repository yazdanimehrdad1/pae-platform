"""
Sites controller.

Sits between the router and the DB/helper layers.
No cache layer — all reads and writes go directly to the DB.
"""

from typing import Literal

import db.site_slds as site_slds_db
import db.sites as sites_db
from helpers.alarms.profile_sync import sync_site_profile_alarms
from helpers.sites import get_complete_site_data_with_points
from logger import get_logger
from schemas.api_models import (
    SiteComprehensiveResponse,
    SiteCreateRequest,
    SiteResponse,
    SiteSldResponse,
    SiteSldUpsertRequest,
    SiteUpdateRequest,
)
from site_profiles.profile_registry import validate_profile_key
from utils.exceptions import ConflictError, NotFoundError

logger = get_logger(__name__)


async def get_all_sites(include_deleted: bool = False) -> list[SiteResponse]:
    return await sites_db.get_all_sites(include_deleted=include_deleted)


async def get_site_by_id(site_id: int, include_deleted: bool = False) -> SiteResponse | None:
    return await sites_db.get_site_by_id(site_id, include_deleted=include_deleted)


async def _ensure_profile_available(profile: str | None, site_id: int | None = None) -> None:
    """A profile belongs to at most one site, soft-deleted ones included (409 if another holds it)."""
    if profile is None:
        return
    holder = await sites_db.get_site_id_by_profile(profile)
    if holder is not None and holder != site_id:
        raise ConflictError(
            f"Profile '{profile}' is already used by site {holder}", payload={"site_id": holder}
        )


async def create_site(site: SiteCreateRequest) -> SiteResponse:
    validate_profile_key(site.profile)
    await _ensure_profile_available(site.profile)
    created = await sites_db.create_site(site)
    # The site gets an alarm row per alarm its profile declares in code.
    await sync_site_profile_alarms(created.site_id)
    return created


async def update_site(site_id: int, site_update: SiteUpdateRequest) -> SiteResponse:
    validate_profile_key(site_update.profile)
    await _ensure_profile_available(site_update.profile, site_id)
    updated = await sites_db.update_site(site_id, site_update)
    if "profile" in site_update.model_fields_set:
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


async def _require_site(site_id: int) -> None:
    if await sites_db.get_site_by_id(site_id) is None:
        raise NotFoundError(f"Site with id {site_id} not found")


async def get_site_sld(site_id: int) -> SiteSldResponse:
    """The site's single line diagram (404 if the site or its diagram is missing)."""
    await _require_site(site_id)
    sld = await site_slds_db.get_site_sld(site_id)
    if sld is None:
        raise NotFoundError(f"Site {site_id} has no single line diagram")
    return sld


async def put_site_sld(site_id: int, request: SiteSldUpsertRequest) -> SiteSldResponse:
    """Create the site's diagram (no revision) or replace the given revision of it (409 if stale)."""
    await _require_site(site_id)
    if request.revision is None:
        return await site_slds_db.create_site_sld(site_id, request.sld)
    return await site_slds_db.update_site_sld(site_id, request.sld, request.revision)


async def delete_site_sld(site_id: int) -> SiteSldResponse:
    """Delete the site's diagram and return what was deleted (404 if it had none)."""
    await _require_site(site_id)
    deleted = await site_slds_db.delete_site_sld(site_id)
    if deleted is None:
        raise NotFoundError(f"Site {site_id} has no single line diagram")
    return deleted
