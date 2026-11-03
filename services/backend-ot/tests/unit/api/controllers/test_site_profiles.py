"""
Unit tests for the site profiles controller.

Guards the listing a client builds its profile choice from: every registered profile appears
once, sorted by key, with the site the database says holds it (null when free), and a holder
of a key that is no longer registered is not listed.
"""

import pytest

import api.controllers.site_profiles as site_profiles_controller
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY


def fake_holders(holders: dict[str, int]):
    async def get_site_ids_by_profile() -> dict[str, int]:
        return holders

    return get_site_ids_by_profile


class TestListSiteProfiles:
    async def test_lists_every_registered_profile_sorted_and_free(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(site_profiles_controller.sites_db, "get_site_ids_by_profile", fake_holders({}))

        profiles = await site_profiles_controller.list_site_profiles()

        assert [profile.key for profile in profiles] == sorted(SITE_PROFILES_BY_KEY)
        assert all(profile.site_id is None for profile in profiles)

    async def test_maps_each_profile_to_its_holder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            site_profiles_controller.sites_db,
            "get_site_ids_by_profile",
            fake_holders({"powerflow_2bess_1pv": 1001, "retired_profile": 7}),
        )

        holders = {profile.key: profile.site_id for profile in await site_profiles_controller.list_site_profiles()}

        assert holders["powerflow_2bess_1pv"] == 1001
        assert holders["alpha_solar"] is None
        assert "retired_profile" not in holders
