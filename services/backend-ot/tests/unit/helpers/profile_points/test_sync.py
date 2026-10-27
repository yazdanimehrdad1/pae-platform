"""
Unit tests for helpers.profile_points.sync.plan_profile_point_sync: which row each declared profile
virtual point gets.

Guards that a declared point is found before anything is created (by its key, then by name), so a
re-run never makes a duplicate; that only a user VIRTUAL point is adopted, never a NATIVE or
STANDARDIZED one or another key's point; and that a missing device skips the point.
"""

from helpers.profile_points.sync import ExistingPoint, plan_profile_point_sync
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import VirtualPointContext
from site_profiles.declarations.virtual_point import SiteVirtualPoint

METER_ID = 7
DEVICES = {"meter": METER_ID}


async def compute(ctx: VirtualPointContext) -> list[TimestampedValue]:
    return []


def declared(key: str = "apparent_power", point_name: str = "apparent_power", device_name: str = "meter") -> SiteVirtualPoint:
    return SiteVirtualPoint(
        key=key, device_name=device_name, point_name=point_name, description="Apparent power", compute=compute
    )


def existing(
    point_id: int, name: str, category: str = "VIRTUAL", key: str | None = None, device_id: int = METER_ID
) -> ExistingPoint:
    return ExistingPoint(id=point_id, device_id=device_id, name=name, category=category, profile_point_key=key)


class TestPlanProfilePointSync:
    def test_point_without_a_row_is_created_on_its_device(self):
        plan = plan_profile_point_sync((declared(),), DEVICES, [existing(1, "voltage", "NATIVE")])
        assert plan.create == {"apparent_power": METER_ID}
        assert (plan.adopt, plan.refresh, plan.name_taken, plan.missing_device) == ({}, {}, [], [])

    def test_point_already_owning_the_key_is_refreshed_not_recreated(self):
        plan = plan_profile_point_sync((declared(),), DEVICES, [existing(5, "renamed_in_ui", key="apparent_power")])
        assert plan.refresh == {"apparent_power": 5}
        assert plan.create == {}

    def test_user_virtual_point_with_the_name_is_adopted(self):
        plan = plan_profile_point_sync((declared(),), DEVICES, [existing(3, "apparent_power")])
        assert plan.adopt == {"apparent_power": 3}
        assert plan.create == {}

    def test_owned_row_wins_over_a_same_named_point(self):
        rows = [existing(3, "apparent_power"), existing(5, "old_name", key="apparent_power")]
        plan = plan_profile_point_sync((declared(),), DEVICES, rows)
        assert plan.refresh == {"apparent_power": 5}
        assert plan.adopt == {}

    def test_native_or_standardized_point_with_the_name_is_not_taken(self):
        for category in ("NATIVE", "STANDARDIZED"):
            plan = plan_profile_point_sync((declared(),), DEVICES, [existing(3, "apparent_power", category)])
            assert plan.name_taken == ["apparent_power"]
            assert (plan.create, plan.adopt) == ({}, {})

    def test_point_owned_by_another_key_is_not_taken(self):
        plan = plan_profile_point_sync((declared(),), DEVICES, [existing(3, "apparent_power", key="other")])
        assert plan.name_taken == ["apparent_power"]

    def test_same_name_on_another_device_does_not_count(self):
        plan = plan_profile_point_sync((declared(),), DEVICES, [existing(3, "apparent_power", device_id=99)])
        assert plan.create == {"apparent_power": METER_ID}

    def test_missing_device_skips_the_point(self):
        plan = plan_profile_point_sync((declared(device_name="gone"),), DEVICES, [])
        assert plan.missing_device == ["apparent_power"]
        assert plan.create == {}

    def test_running_the_plan_on_its_own_result_changes_nothing_but_refresh(self):
        first = plan_profile_point_sync((declared(),), DEVICES, [])
        created = [existing(10, "apparent_power", key=key) for key in first.create]
        second = plan_profile_point_sync((declared(),), DEVICES, created)
        assert second.create == {}
        assert second.refresh == {"apparent_power": 10}
