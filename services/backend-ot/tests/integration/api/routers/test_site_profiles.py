"""
Integration tests for /api/site-profiles.

Guards the profile listing against a real database: every registered profile is listed once,
in key order, with the site holding it (null when free), and a soft-deleted site still holds
its profile (the one-site-per-profile rule counts it).
"""

from pydantic import TypeAdapter

from integration.factories import create_site
from schemas.site_profiles import SiteProfileInfo
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY

PROFILE_LIST = TypeAdapter(list[SiteProfileInfo])


async def list_profiles(client) -> list[SiteProfileInfo]:
    response = await client.get("/api/site-profiles")
    assert response.status_code == 200, response.text
    return PROFILE_LIST.validate_python(response.json())


class TestListSiteProfiles:
    async def test_lists_every_registered_profile_free_when_no_site_holds_it(self, client):
        profiles = await list_profiles(client)
        assert [profile.key for profile in profiles] == sorted(SITE_PROFILES_BY_KEY)
        assert all(profile.site_id is None for profile in profiles)

    async def test_names_the_site_holding_a_profile(self, client):
        site = await create_site(client, profile="alpha_solar")
        await create_site(client, name="No profile")

        holders = {profile.key: profile.site_id for profile in await list_profiles(client)}
        assert holders["alpha_solar"] == site.site_id
        assert holders["powerflow_2bess_1pv"] is None

    async def test_a_soft_deleted_site_still_holds_its_profile(self, client):
        site = await create_site(client, profile="alpha_solar")
        response = await client.delete(f"/api/sites/{site.site_id}", params={"mode": "soft"})
        assert response.status_code == 200, response.text

        holders = {profile.key: profile.site_id for profile in await list_profiles(client)}
        assert holders["alpha_solar"] == site.site_id
