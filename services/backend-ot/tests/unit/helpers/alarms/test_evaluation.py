"""
Unit tests for helpers.alarms.evaluation._observe with PROFILE alarms.

Guards that a profile alarm's check result becomes the observation and that the delays declared
on its SiteAlarm (delay_sec, clear_delay_sec) reach the state machine, so a profile alarm with a
delay goes pending first and raises only once the delay has passed.
"""

from datetime import UTC, datetime, timedelta

from helpers.alarms.engine import AlarmState, step
from helpers.alarms.evaluation import _observe
from schemas.db_models.orm_models import AlarmDefinition
from schemas.site_profiles import AlarmCheck, AlarmContext
from site_profiles.declarations.alarm import SiteAlarm
from site_profiles.declarations.profile import SiteProfile
from unit.site_fixtures import make_site

NOW = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)


async def always_active(ctx: AlarmContext) -> AlarmCheck:
    return AlarmCheck(active=True, value=7.0, device_id=3)


def profile(delay_sec: int = 0, clear_delay_sec: int = 0) -> SiteProfile:
    return SiteProfile(key="one", endpoints=(), alarms=(SiteAlarm(
        key="k", name="k", severity="MEDIUM", message="m", evaluate=always_active,
        delay_sec=delay_sec, clear_delay_sec=clear_delay_sec,
    ),))


def definition(key: str = "k") -> AlarmDefinition:
    return AlarmDefinition(id=1, site_id=1, source="PROFILE", profile_alarm_key=key, name=key, kind="profile",
                           severity="MEDIUM", message="m", enabled=True)


def context() -> AlarmContext:
    return AlarmContext(site=make_site(profile="one"), devices=[], now=NOW)


async def observe(site_profile: SiteProfile | None, key: str = "k"):
    return await _observe(definition(key), context(), site_profile, {}, {}, {}, NOW)


class TestObserveProfileAlarm:
    async def test_declared_delays_are_returned_with_the_check(self):
        observation, delay, clear_delay = await observe(profile(delay_sec=60, clear_delay_sec=30))
        assert observation is not None
        assert (observation.holds, observation.cleared, observation.value, observation.device_id) == (True, False, 7.0, 3)
        assert (delay, clear_delay) == (timedelta(seconds=60), timedelta(seconds=30))

    async def test_no_declared_delay_is_zero(self):
        _, delay, clear_delay = await observe(profile())
        assert (delay, clear_delay) == (timedelta(0), timedelta(0))

    async def test_alarm_no_longer_declared_observes_nothing(self):
        assert await observe(profile(), key="gone") == (None, timedelta(0), timedelta(0))
        assert await observe(None) == (None, timedelta(0), timedelta(0))

    async def test_a_delayed_profile_alarm_raises_only_after_its_delay(self):
        observation, delay, clear_delay = await observe(profile(delay_sec=60))
        pending, transition = step(AlarmState(), observation, delay, NOW, clear_delay)
        assert transition is None and pending.condition_since == NOW
        _, transition = step(pending, observation, delay, NOW + timedelta(seconds=44), clear_delay)
        assert transition is None
        _, transition = step(pending, observation, delay, NOW + timedelta(seconds=66), clear_delay)
        assert transition is not None and transition.kind == "raise"
