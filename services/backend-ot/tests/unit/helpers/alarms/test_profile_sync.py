"""
Unit tests for helpers.alarms.profile_sync.plan_profile_alarm_sync.

Guards how a site's PROFILE alarm rows follow the code: a newly declared alarm is created, a
changed name/severity/message is refreshed, a retired one comes back when re-declared, one the
profile no longer declares is retired (never hard-deleted), unchanged rows are left alone, and an
alarm whose name a user alarm already took is skipped rather than breaking the sync.
"""

from helpers.alarms.profile_sync import ExistingProfileAlarm, plan_profile_alarm_sync
from schemas.site_profiles import AlarmCheck, AlarmContext
from site_profiles.declarations.alarm import SiteAlarm


async def check(ctx: AlarmContext) -> AlarmCheck:
    return AlarmCheck(active=False)


def declared(key: str, name: str | None = None, message: str = "m") -> SiteAlarm:
    return SiteAlarm(key=key, name=name or key, severity="fault", message=message, evaluate=check)


def stored(key: str, name: str | None = None, message: str = "m", deleted: bool = False) -> ExistingProfileAlarm:
    return ExistingProfileAlarm(key=key, name=name or key, severity="fault", message=message, deleted=deleted)


class TestPlanProfileAlarmSync:
    def test_new_declared_alarm_is_created(self):
        plan = plan_profile_alarm_sync([], (declared("a"),), set())
        assert (plan.create, plan.refresh, plan.retire) == (["a"], [], [])

    def test_unchanged_row_is_left_alone(self):
        plan = plan_profile_alarm_sync([stored("a")], (declared("a"),), set())
        assert (plan.create, plan.refresh, plan.retire) == ([], [], [])

    def test_changed_text_is_refreshed_and_a_retired_row_restored(self):
        plan = plan_profile_alarm_sync(
            [stored("a", message="old"), stored("b", deleted=True)], (declared("a", message="new"), declared("b")), set()
        )
        assert plan.refresh == ["a", "b"]

    def test_alarm_no_longer_declared_is_retired_once(self):
        plan = plan_profile_alarm_sync([stored("a"), stored("b", deleted=True)], (), set())
        assert plan.retire == ["a"]

    def test_name_taken_by_a_user_alarm_is_skipped(self):
        plan = plan_profile_alarm_sync([], (declared("a", name="Shared_Name"),), {"shared_name"})
        assert (plan.create, plan.name_taken) == ([], ["a"])

    def test_own_row_keeps_its_name_even_if_a_user_alarm_looks_alike(self):
        # The row already holds the name, so a user alarm can't have it too; nothing to skip.
        plan = plan_profile_alarm_sync([stored("a", name="x")], (declared("a", name="x"),), {"x"})
        assert plan.name_taken == []
