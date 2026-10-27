"""
Unit tests for profile virtual points: site_profiles.declarations.virtual_point.SiteVirtualPoint and
the startup checks in site_profiles.profile_registry.validate_site_virtual_points.

Guards that a profile virtual point's compute function is async, lives in site_profiles/common/ or
its own profile's package, returns list[TimestampedValue], and that keys and (device, point name)
targets are unique per profile; and that the registered profiles pass these checks.

Test functions are defined here, so each case sets __module__ to where the function would live.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta

import pytest
from pydantic import ValidationError

from schemas.internal_models import TimestampedValue
from schemas.site_profiles import VirtualPointContext
from site_profiles.declarations.profile import SiteProfile
from site_profiles.declarations.virtual_point import SiteVirtualPoint
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY, validate_site_virtual_points
from utils.exceptions import SiteProfileConfigError

ComputeFunction = Callable[[VirtualPointContext], Awaitable[list[TimestampedValue]]]


def make_compute(module: str, returns: object = list[TimestampedValue]) -> ComputeFunction:
    async def compute(ctx: VirtualPointContext) -> list[TimestampedValue]:
        return []

    compute.__annotations__["return"] = returns
    compute.__module__ = module
    return compute


def virtual_point(
    key: str = "apparent_power",
    device_name: str = "meter",
    point_name: str = "apparent_power",
    module: str = "site_profiles.individual_sites.one.virtual_points",
    returns: object = list[TimestampedValue],
) -> SiteVirtualPoint:
    return SiteVirtualPoint(
        key=key, device_name=device_name, point_name=point_name, unit="kVA", description="Apparent power",
        compute=make_compute(module, returns),
    )


def profile(*points: SiteVirtualPoint, key: str = "one") -> SiteProfile:
    return SiteProfile(key=key, endpoints=(), virtual_points=points)


class TestSiteVirtualPointShape:
    def test_compute_must_be_async(self):
        def not_async(ctx: VirtualPointContext) -> list[TimestampedValue]:
            return []

        with pytest.raises(ValidationError, match="async def"):
            SiteVirtualPoint(key="k", device_name="d", point_name="p", description="x", compute=not_async)

    def test_description_is_required(self):
        with pytest.raises(ValidationError, match="description"):
            SiteVirtualPoint(key="k", device_name="d", point_name="p", compute=make_compute("x"))
        with pytest.raises(ValidationError, match="description"):
            SiteVirtualPoint(key="k", device_name="d", point_name="p", description="", compute=make_compute("x"))

    @pytest.mark.parametrize("key", ["Apparent", "apparent-power", "has space", ""])
    def test_key_is_snake_case(self, key: str):
        with pytest.raises(ValidationError):
            virtual_point(key=key)

    def test_backfill_defaults_to_none_and_cannot_be_negative(self):
        assert virtual_point().backfill == timedelta(0)
        with pytest.raises(ValidationError):
            SiteVirtualPoint(
                key="k", device_name="d", point_name="p", description="x", compute=make_compute("x"),
                backfill=timedelta(seconds=-1),
            )


class TestValidateSiteVirtualPoints:
    def test_compute_in_own_package_or_common_is_accepted(self):
        validate_site_virtual_points((profile(
            virtual_point("a", point_name="a", module="site_profiles.individual_sites.one.virtual_points"),
            virtual_point("b", point_name="b", module="site_profiles.common.virtual_points"),
        ),))

    def test_compute_of_another_site_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="belongs in"):
            validate_site_virtual_points((profile(virtual_point(module="site_profiles.individual_sites.two.vp")),))

    @pytest.mark.parametrize("returns", [list[float], TimestampedValue, list[TimestampedValue] | None])
    def test_compute_must_return_a_list_of_timestamped_values(self, returns: object):
        with pytest.raises(SiteProfileConfigError, match="not list\\[TimestampedValue\\]"):
            validate_site_virtual_points((profile(virtual_point(returns=returns)),))

    def test_duplicate_key_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="key 'a' is declared twice"):
            validate_site_virtual_points((profile(virtual_point("a", point_name="x"), virtual_point("a", point_name="y")),))

    def test_two_keys_storing_into_one_point_are_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="'x' on device 'meter' is declared twice"):
            validate_site_virtual_points((profile(virtual_point("a", point_name="x"), virtual_point("b", point_name="x")),))

    def test_same_point_name_on_two_devices_is_accepted(self):
        validate_site_virtual_points((profile(
            virtual_point("a", device_name="meter_1", point_name="x"),
            virtual_point("b", device_name="meter_2", point_name="x"),
        ),))

    def test_registered_profiles_pass_and_alpha_solar_declares_poi_apparent_power(self):
        validate_site_virtual_points(tuple(SITE_PROFILES_BY_KEY.values()))
        alpha = SITE_PROFILES_BY_KEY["alpha_solar"]
        assert [declared.key for declared in alpha.virtual_points] == ["poi_apparent_power"]
        assert alpha.find_virtual_point("poi_apparent_power") is not None
        assert alpha.find_virtual_point("gone") is None
