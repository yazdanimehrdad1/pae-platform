"""
Unit tests for profile device health checks: site_profiles.site_health.DeviceHealthCheck and the
startup checks in site_profiles.profile_registry.validate_site_device_health.

Guards that a check is async, lives in site_profiles/common/ or its own profile's package, returns
DeviceHealth, that a profile declares at most one check per SLD element type, and that the
registered profiles pass these checks.

Test checks are defined here, so each case sets __module__ to where the check would live.
"""

from collections.abc import Awaitable, Callable

import pytest
from pydantic import BaseModel, ValidationError

from schemas.site_profiles import DeviceHealth, DeviceHealthContext
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY, validate_site_device_health
from site_profiles.site_endpoint import SiteProfile
from site_profiles.site_health import DeviceHealthCheck, HealthNodeType
from utils.exceptions import SiteProfileConfigError


def make_check(
    module: str, returns: type[BaseModel] = DeviceHealth
) -> Callable[[DeviceHealthContext], Awaitable[DeviceHealth]]:
    async def check(ctx: DeviceHealthContext) -> DeviceHealth:
        return DeviceHealth(healthy=True)

    check.__annotations__["return"] = returns
    check.__module__ = module
    return check


def health(
    node_type: HealthNodeType = "bess",
    module: str = "site_profiles.individual_sites.one.health",
    returns: type[BaseModel] = DeviceHealth,
) -> DeviceHealthCheck:
    return DeviceHealthCheck(node_type=node_type, evaluate=make_check(module, returns))


def profile(*checks: DeviceHealthCheck) -> SiteProfile:
    return SiteProfile(key="one", endpoints=(), device_health=checks)


class TestDeviceHealthCheckShape:
    def test_check_must_be_async(self):
        def not_async(ctx: DeviceHealthContext) -> DeviceHealth:
            return DeviceHealth(healthy=True)

        with pytest.raises(ValidationError, match="async def"):
            DeviceHealthCheck(node_type="pv", evaluate=not_async)

    def test_only_bess_and_pv_show_health(self):
        with pytest.raises(ValidationError):
            DeviceHealthCheck.model_validate(
                {"node_type": "meter", "evaluate": make_check("site_profiles.common.health")}
            )

    def test_profile_finds_its_check_by_type(self):
        bess = health("bess")
        assert profile(bess).find_health_check("bess") is bess
        assert profile(bess).find_health_check("pv") is None


class TestValidateSiteDeviceHealth:
    def test_check_in_own_package_or_common_is_accepted(self):
        validate_site_device_health((profile(
            health("bess", "site_profiles.individual_sites.one.health"),
            health("pv", "site_profiles.common.health"),
        ),))

    def test_check_in_another_profiles_package_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="belongs in"):
            validate_site_device_health((profile(health(module="site_profiles.individual_sites.two.health")),))

    def test_check_must_return_device_health(self):
        class Other(BaseModel):
            healthy: bool = True

        with pytest.raises(SiteProfileConfigError, match="not DeviceHealth"):
            validate_site_device_health((profile(health(returns=Other)),))

    def test_two_checks_for_one_type_are_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="declared twice"):
            validate_site_device_health((profile(health("bess"), health("bess")),))

    def test_registered_profiles_pass(self):
        validate_site_device_health(tuple(SITE_PROFILES_BY_KEY.values()))
        assert SITE_PROFILES_BY_KEY["alpha_solar"].find_health_check("bess") is not None
