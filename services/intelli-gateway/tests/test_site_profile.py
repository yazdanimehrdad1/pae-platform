"""Site profiles: the gateway's approved copy of a site's facts, kept in step with backend-ot only
through a site admin's approval, and the gate the AI reads site data through.

Invariant guarded:
- a sync only records what backend-ot has; nothing reaches the AI until it is approved;
- approval takes exactly the chosen changes (a new site's first approval must include the site),
  refuses unknown ids and changes reviewed against an older read of backend-ot;
- a device rename is one device change: points keep their approved names until it is approved;
- the AI sees no site that isn't onboarded, and of an onboarded one only approved devices and
  points (facts, live values, history, alarms, comms), with values whose definition changed in
  backend-ot flagged `definition_pending_review`.
"""

from datetime import timedelta

import pytest
from doubles.knowledge_store import InMemoryKnowledgeStore
from doubles.models import FakeSite
from doubles.site_profile_store import InMemorySiteProfileStore
from fakes import FIXED_NOW, as_dict, fixed_clock, make_ctx
from site_profile_fakes import SITE_ID, backend, mesa

from intelli_gateway.schemas.site_profile import ChangeKind, ChangeTarget, ProfileVersion
from intelli_gateway.site_profile.gate import ApprovedSiteDataConnector
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.tools.catalog import build_local_tools
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.local_provider import LocalToolProvider
from intelli_gateway.utils.exceptions import ConflictError, InvalidRequestError, NotFoundError

ADMIN = "admin@example.com"


class Platform:
    """One profile store; backend-ot can be swapped to show what it has "now"."""

    def __init__(self) -> None:
        self.store = InMemorySiteProfileStore()
        self.now(mesa())

    def now(self, site: FakeSite) -> None:
        source = backend(site)
        # cache_ttl_s=0: every read sees the latest approval and sync.
        self.profiles = SiteProfileService(self.store, source, fixed_clock, cache_ttl_s=0)
        self.gate = ApprovedSiteDataConnector(source, self.profiles)

    async def onboard(self) -> ProfileVersion:
        await self.profiles.sync_site(SITE_ID)
        return await self.profiles.approve(SITE_ID, ADMIN)

    async def change_to(self, site: FakeSite) -> list[str]:
        """backend-ot now has `site`; sync and return the pending change ids."""
        self.now(site)
        pending = await self.profiles.sync_site(SITE_ID)
        return [change.change_id for change in pending.changes]


@pytest.fixture
def platform() -> Platform:
    return Platform()


class TestOnboarding:
    async def test_a_synced_site_is_all_pending_until_approved(self, platform: Platform) -> None:
        pending = await platform.profiles.sync_site(SITE_ID)
        assert pending.approved_version is None
        assert [(c.change_id, c.kind) for c in pending.changes] == [
            ("site", ChangeKind.ADDED),
            ("device:1", ChangeKind.ADDED),
            ("topology", ChangeKind.ADDED),
        ]
        assert "3 points" in pending.changes[1].summary
        assert await platform.gate.get_site(SITE_ID) is None  # the AI doesn't see it yet

        profile = await platform.profiles.approve(SITE_ID, ADMIN)
        assert (profile.version, profile.approved_by) == (1, ADMIN)
        assert [point.name for point in profile.catalog.points] == [
            "M1.Fault",
            "M1.Power",
            "M1.Status",
        ]
        assert (await platform.profiles.pending_changes(SITE_ID)).changes == ()
        site = await platform.gate.get_site(SITE_ID)
        assert site is not None and site.name == "Mesa Test"

    async def test_nothing_to_review_before_a_sync(self, platform: Platform) -> None:
        with pytest.raises(NotFoundError):
            await platform.profiles.pending_changes(SITE_ID)
        with pytest.raises(NotFoundError):
            await platform.profiles.approve(SITE_ID, ADMIN)
        with pytest.raises(NotFoundError):
            await platform.profiles.sync_site(999)  # backend-ot has no such site

    async def test_a_first_approval_must_include_the_site(self, platform: Platform) -> None:
        await platform.profiles.sync_site(SITE_ID)
        with pytest.raises(InvalidRequestError, match="'site'"):
            await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["device:1"])
        profile = await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["site"])
        assert profile.catalog.devices == ()  # onboarded with no devices approved yet
        assert await platform.gate.list_points(SITE_ID) == []

    async def test_unknown_ids_and_empty_approvals_are_refused(self, platform: Platform) -> None:
        await platform.onboard()
        with pytest.raises(InvalidRequestError, match="no changes"):
            await platform.profiles.approve(SITE_ID, ADMIN)
        await platform.change_to(mesa(power_unit="W"))
        with pytest.raises(InvalidRequestError, match="device:7"):
            await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["device:7"])
        assert (await platform.profiles.get_profile(SITE_ID)).version == 1

    async def test_changes_reviewed_against_an_older_read_are_refused(
        self, platform: Platform
    ) -> None:
        reviewed = await platform.profiles.sync_site(SITE_ID)
        with pytest.raises(ConflictError):
            await platform.profiles.approve(
                SITE_ID, ADMIN, expected_fetched_at=reviewed.fetched_at - timedelta(minutes=15)
            )
        profile = await platform.profiles.approve(
            SITE_ID, ADMIN, expected_fetched_at=reviewed.fetched_at
        )
        assert profile.version == 1


class TestChanges:
    async def test_approval_takes_only_the_chosen_changes(self, platform: Platform) -> None:
        await platform.onboard()
        pending = await platform.change_to(mesa(power_unit="W", with_m2=True))
        assert pending == ["point:1:Power", "device:2", "topology"]
        profile = await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["point:1:Power"])
        assert profile.version == 2 and profile.change_ids == ("point:1:Power",)
        power = next(p for p in profile.catalog.points if p.name == "M1.Power")
        assert power.unit == "W"
        assert [device.device_id for device in profile.catalog.devices] == [1]
        still = [c.change_id for c in (await platform.profiles.pending_changes(SITE_ID)).changes]
        assert still == ["device:2", "topology"]

    async def test_a_new_device_comes_with_its_points(self, platform: Platform) -> None:
        await platform.onboard()
        await platform.change_to(mesa(with_m2=True))
        profile = await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["device:2"])
        assert "M2.Fault" in [point.name for point in profile.catalog.points]
        assert len(profile.catalog.points) == 6

    async def test_a_removed_device_takes_its_points(self, platform: Platform) -> None:
        platform.now(mesa(with_m2=True))
        await platform.onboard()
        pending = await platform.change_to(mesa())
        assert "device:2" in pending
        change = next(
            c
            for c in (await platform.profiles.pending_changes(SITE_ID)).changes
            if c.change_id == "device:2"
        )
        assert change.kind is ChangeKind.REMOVED
        profile = await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["device:2"])
        assert all(point.device_id == 1 for point in profile.catalog.points)

    async def test_a_rename_is_one_device_change(self, platform: Platform) -> None:
        await platform.onboard()
        pending = await platform.profiles.sync_site(SITE_ID)
        assert pending.changes == ()
        await platform.change_to(mesa(m1_name="Meter1"))
        changes = (await platform.profiles.pending_changes(SITE_ID)).changes
        assert [(c.change_id, c.target, c.fields) for c in changes] == [
            ("device:1", ChangeTarget.DEVICE, ("name",)),
            ("topology", ChangeTarget.TOPOLOGY, ()),
        ]
        # Until it is approved the AI keeps the approved names.
        assert "M1.Power" in [point.name for point in await platform.gate.list_points(SITE_ID)]
        profile = await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["device:1"])
        assert [point.name for point in profile.catalog.points] == [
            "Meter1.Fault",
            "Meter1.Power",
            "Meter1.Status",
        ]
        assert {point.device_name for point in profile.catalog.points} == {"Meter1"}

    async def test_status_and_versions_show_the_history(self, platform: Platform) -> None:
        await platform.onboard()
        await platform.change_to(mesa(power_unit="W", with_m2=True))
        await platform.profiles.approve(SITE_ID, ADMIN, change_ids=["device:2"])
        (status,) = await platform.profiles.statuses()
        assert (status.site_id, status.name, status.approved_version) == (SITE_ID, "Mesa Test", 2)
        assert status.pending_changes == 2  # M1.Power's unit and the topology
        assert status.fetched_at == FIXED_NOW
        versions = await platform.profiles.versions(SITE_ID)
        assert [version.version for version in versions] == [2, 1]
        with pytest.raises(NotFoundError):
            await platform.profiles.versions(999)


class TestWhatTheAiSees:
    async def test_a_site_that_isnt_onboarded_does_not_exist(self, platform: Platform) -> None:
        await platform.profiles.sync_site(SITE_ID)
        assert await platform.gate.list_sites() == []
        assert await platform.gate.list_devices(SITE_ID) == []
        assert await platform.gate.get_latest_many(SITE_ID, ["M1.Power"]) == {"M1.Power": None}
        assert (
            await platform.gate.get_history(
                SITE_ID, "M1.Power", FIXED_NOW - timedelta(hours=1), FIXED_NOW
            )
            is None
        )
        active = await platform.gate.get_active_alarms(SITE_ID)
        assert (active.events, active.point_alarms) == ([], [])
        assert await platform.gate.get_device_comms(SITE_ID) == []

    async def test_an_unapproved_device_stays_invisible(self, platform: Platform) -> None:
        await platform.onboard()
        await platform.change_to(mesa(with_m2=True))
        gate = platform.gate
        assert [device.device_id for device in await gate.list_devices(SITE_ID)] == [1]
        latest = await gate.get_latest_many(SITE_ID, ["M1.Power", "M2.Power"])
        assert latest["M2.Power"] is None
        power = latest["M1.Power"]
        assert power is not None and power.value == 120.0
        active = await gate.get_active_alarms(SITE_ID)
        assert [event.alarm_name for event in active.events] == ["Grid event"]  # site-level kept
        assert [alarm.point_name for alarm in active.point_alarms] == ["M1.Fault"]
        assert (
            await gate.get_alarm_events(SITE_ID, FIXED_NOW - timedelta(hours=2), FIXED_NOW, 2) == []
        )
        assert [entry.device_id for entry in await gate.get_device_comms(SITE_ID)] == [1]

    async def test_a_changed_definition_is_flagged_until_approved(self, platform: Platform) -> None:
        await platform.onboard()
        await platform.change_to(mesa(status_labels={0: "stopped", 1: "running"}))
        latest = await platform.gate.get_latest_many(SITE_ID, ["M1.Status", "M1.Power"])
        status, power = latest["M1.Status"], latest["M1.Power"]
        assert status is not None and status.definition_pending_review
        assert power is not None and not power.definition_pending_review
        await platform.profiles.approve(SITE_ID, ADMIN)
        status = (await platform.gate.get_latest_many(SITE_ID, ["M1.Status"]))["M1.Status"]
        assert status is not None and not status.definition_pending_review

    async def test_a_pending_rename_keeps_the_approved_names(self, platform: Platform) -> None:
        await platform.onboard()
        await platform.change_to(mesa(m1_name="Meter1"))
        gate = platform.gate
        latest = await gate.get_latest_many(SITE_ID, ["M1.Power", "Meter1.Power"])
        power = latest["M1.Power"]
        assert power is not None and power.name == "M1.Power" and power.value == 120.0
        assert latest["Meter1.Power"] is None
        start, end = FIXED_NOW - timedelta(hours=1), FIXED_NOW
        assert await gate.get_history(SITE_ID, "M1.Power", start, end)
        assert await gate.get_history(SITE_ID, "Meter1.Power", start, end) is None
        active = await gate.get_active_alarms(SITE_ID)
        assert [alarm.point_name for alarm in active.point_alarms] == ["M1.Fault"]

    async def test_the_tools_pass_the_flag_to_the_model(self, platform: Platform) -> None:
        await platform.onboard()
        await platform.change_to(mesa(power_unit="W"))
        limits = SiteToolLimits(
            max_rows=50, history_samples=12, history_max_days=31, max_text_chars=20_000
        )
        provider = LocalToolProvider(
            build_local_tools(platform.gate, InMemoryKnowledgeStore([]), limits), 20_000
        )
        result = await provider.call_tool(
            "get_point_values",
            {"point_names": ["M1.Power", "M2.Power"]},
            make_ctx(site_id=SITE_ID),
        )
        assert not result.is_error
        content = as_dict(result.content)
        assert content["values"] == [
            {
                "name": "M1.Power",
                "device_id": 1,
                "value": 120.0,
                "unit": "W",
                "timestamp": FIXED_NOW.isoformat().replace("+00:00", "Z"),
                "quality": "good",
                "age_s": 0.0,
                "definition_pending_review": True,
            }
        ]
        assert content["not_found"] == ["M2.Power"]  # an unapproved device's point
