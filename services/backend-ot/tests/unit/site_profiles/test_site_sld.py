"""
Unit tests for site_profiles.site_sld.

Guards loading a profile's sld.json: a missing, malformed or invalid file is a
SiteProfileConfigError naming the file (so the app refuses to start), and every SLD a
registered profile ships is valid.
"""

from pathlib import Path

import pytest

from schemas.site_profiles import SiteSld
from site_profiles.profile_registry import ALL_SITE_PROFILES, SITE_PROFILES_BY_KEY
from site_profiles.site_sld import load_site_sld
from utils.exceptions import SiteProfileConfigError

VALID_SLD = '{"schema_version": 1, "nodes": [{"id": "utility", "type": "grid", "name": "Utility", "col": 0, "row": 0}]}'


class TestLoadSiteSld:
    def test_valid_file_loads(self, tmp_path: Path):
        path = tmp_path / "sld.json"
        path.write_text(VALID_SLD, encoding="utf-8")
        sld = load_site_sld(path)
        assert isinstance(sld, SiteSld)
        assert sld.nodes[0].id == "utility"

    def test_missing_file_names_the_path(self, tmp_path: Path):
        path = tmp_path / "missing.json"
        with pytest.raises(SiteProfileConfigError, match="missing.json"):
            load_site_sld(path)

    def test_malformed_json_names_the_path(self, tmp_path: Path):
        path = tmp_path / "sld.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(SiteProfileConfigError, match="Invalid single line diagram"):
            load_site_sld(path)

    def test_schema_violation_is_rejected(self, tmp_path: Path):
        path = tmp_path / "sld.json"
        path.write_text('{"schema_version": 1, "nodes": []}', encoding="utf-8")
        with pytest.raises(SiteProfileConfigError, match="Invalid single line diagram"):
            load_site_sld(path)


class TestShippedSlds:
    def test_alpha_solar_ships_an_sld(self):
        sld = SITE_PROFILES_BY_KEY["alpha_solar"].sld
        assert sld is not None
        assert any(node.type == "grid" for node in sld.nodes)

    def test_default_profile_has_no_sld(self):
        assert SITE_PROFILES_BY_KEY["default"].sld is None

    @pytest.mark.parametrize(
        "profile",
        [profile for profile in ALL_SITE_PROFILES if profile.sld is not None],
        ids=lambda profile: profile.key,
    )
    def test_every_shipped_sld_connects_every_element(self, profile):
        # Already validated at import; also guard against an element nothing connects to.
        sld = profile.sld
        connected = {
            end for connection in sld.connections for end in (connection.from_id, connection.to_id)
        }
        element_ids = {node.id for node in sld.nodes} | {bus.id for bus in sld.buses}
        assert element_ids <= connected, f"unconnected: {sorted(element_ids - connected)}"
