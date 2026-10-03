"""
Unit tests for profile alarms: site_profiles.site_alarm.SiteAlarm and the startup checks in
site_profiles.profile_registry.validate_site_alarms.

Guards that a profile alarm's check is async, lives in site_profiles/common/ or its own profile's
package, returns AlarmCheck, and that keys and names (ignoring
case) are unique per profile; and that the registered profiles pass these checks.

Test checks are defined here, so each case sets __module__ to where the check would live.
"""

from collections.abc import Awaitable, Callable

import pytest
from pydantic import BaseModel, ValidationError

from schemas.site_profiles import AlarmCheck, AlarmContext
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY, validate_site_alarms
from site_profiles.site_alarm import SiteAlarm
from site_profiles.site_endpoint import SiteProfile
from utils.exceptions import SiteProfileConfigError


def make_check(module: str, returns: type[BaseModel] = AlarmCheck) -> Callable[[AlarmContext], Awaitable[AlarmCheck]]:
    async def check(ctx: AlarmContext) -> AlarmCheck:
        return AlarmCheck(active=False)

    check.__annotations__["return"] = returns
    check.__module__ = module
    return check


def alarm(key: str = "too_hot", name: str = "too_hot", module: str = "site_profiles.individual_sites.one.alarms",
          returns: type[BaseModel] = AlarmCheck) -> SiteAlarm:
    return SiteAlarm(key=key, name=name, severity="warning", message="It is too hot", evaluate=make_check(module, returns))


def profile(*alarms: SiteAlarm, key: str = "one") -> SiteProfile:
    return SiteProfile(key=key, endpoints=(), alarms=alarms)


class TestSiteAlarmShape:
    def test_check_must_be_async(self):
        def not_async(ctx: AlarmContext) -> AlarmCheck:
            return AlarmCheck(active=False)

        with pytest.raises(ValidationError, match="async def"):
            SiteAlarm(key="k", name="k", severity="fault", message="m", evaluate=not_async)

    @pytest.mark.parametrize(("key", "name"), [("Too_Hot", "ok"), ("too-hot", "ok"), ("ok", "1_bad"), ("ok", "has space")])
    def test_key_is_snake_case_and_name_an_identifier(self, key: str, name: str):
        with pytest.raises(ValidationError):
            alarm(key=key, name=name)


class TestValidateSiteAlarms:
    def test_check_in_own_package_or_common_is_accepted(self):
        validate_site_alarms((profile(
            alarm("a", "a", "site_profiles.individual_sites.one.alarms"),
            alarm("b", "b", "site_profiles.common.alarms"),
        ),))

    def test_check_of_another_site_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="belongs in"):
            validate_site_alarms((profile(alarm(module="site_profiles.individual_sites.two.alarms")),))

    def test_check_must_return_alarm_check(self):
        class Other(BaseModel):
            active: bool = False

        with pytest.raises(SiteProfileConfigError, match="not AlarmCheck"):
            validate_site_alarms((profile(alarm(returns=Other)),))

    def test_duplicate_key_or_name_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="key 'a' is declared twice"):
            validate_site_alarms((profile(alarm("a", "x"), alarm("a", "y")),))
        with pytest.raises(SiteProfileConfigError, match="name 'X' is declared twice"):
            validate_site_alarms((profile(alarm("a", "x"), alarm("b", "X")),))

    def test_registered_profiles_pass_and_alpha_solar_declares_an_alarm(self):
        validate_site_alarms(tuple(SITE_PROFILES_BY_KEY.values()))
        assert [declared.key for declared in SITE_PROFILES_BY_KEY["alpha_solar"].alarms] == ["placeholder_profile_alarm_1"]
        assert SITE_PROFILES_BY_KEY["alpha_solar"].find_alarm("placeholder_profile_alarm_1") is not None
        assert SITE_PROFILES_BY_KEY["alpha_solar"].find_alarm("gone") is None
