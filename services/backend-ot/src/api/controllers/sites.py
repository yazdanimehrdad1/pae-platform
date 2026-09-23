"""
Sites controller.

Sits between the router and the DB/helper layers.
No cache layer — all reads and writes go directly to the DB.
"""

from typing import Literal

import db.sites as sites_db
from helpers.sites import get_complete_site_data_with_points
from logger import get_logger
from schemas.api_models import (
    SiteComprehensiveResponse,
    SiteCreateRequest,
    SiteResponse,
    SiteUpdateRequest,
)

logger = get_logger(__name__)


async def get_all_sites(include_deleted: bool = False) -> list[SiteResponse]:
    return await sites_db.get_all_sites(include_deleted=include_deleted)


async def get_site_by_id(site_id: int, include_deleted: bool = False) -> SiteResponse | None:
    return await sites_db.get_site_by_id(site_id, include_deleted=include_deleted)


async def create_site(site: SiteCreateRequest) -> SiteResponse:
    return await sites_db.create_site(site)


async def update_site(site_id: int, site_update: SiteUpdateRequest) -> SiteResponse:
    return await sites_db.update_site(site_id, site_update)


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
