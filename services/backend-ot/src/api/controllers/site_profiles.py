"""
Site profiles controller.

Lists the profiles registered in site_profiles/profile_registry.py, each with the site that
holds it (a profile belongs to at most one site), so a client can offer the free ones.
"""

import db.sites as sites_db
from schemas.site_profiles import SiteProfileInfo
from site_profiles.profile_registry import ALL_SITE_PROFILES


async def list_site_profiles() -> list[SiteProfileInfo]:
    holders = await sites_db.get_site_ids_by_profile()
    return [
        SiteProfileInfo(key=profile.key, site_id=holders.get(profile.key))
        for profile in sorted(ALL_SITE_PROFILES, key=lambda profile: profile.key)
    ]
