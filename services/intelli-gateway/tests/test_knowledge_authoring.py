"""Authoring a site's engineer knowledge (drafts, publish for the whole site) and what the AI reads.

Invariant guarded:
- edits go to a draft; the AI reads only the published version, and a publish takes the whole
  draft at once; an edit or publish made against an older draft revision is refused
- only approved devices and points take knowledge; secrets, credentials and IP addresses are
  refused; one guide entry per state/bit/code
- guides are kept by the point's name within its device: an approved device rename keeps them,
  and the AI sees them under the new qualified name; knowledge about devices no longer approved
  is kept but not served
- single draft changes can be put back as published; restoring an old version makes a new one
- coverage lists the status/alarm points that still need a guide
"""

import pytest
from doubles.knowledge_authoring_store import InMemoryKnowledgeAuthoringStore
from doubles.models import FakeSite
from doubles.site_profile_store import InMemorySiteProfileStore
from fakes import FIXED_NOW, fixed_clock
from site_profile_fakes import SITE_ID, backend, mesa

from intelli_gateway.knowledge.loader import render_knowledge
from intelli_gateway.knowledge.published_store import PublishedKnowledgeStore
from intelli_gateway.knowledge.service import DocumentContent, GuideContent, SiteKnowledgeService
from intelli_gateway.schemas.knowledge import (
    DeviceRating,
    GuideSeverity,
    KnowledgeKind,
    LimitCondition,
    LimitGuide,
    SiteKnowledge,
    StateGuide,
    StateKind,
)
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.utils.exceptions import ConflictError, InvalidRequestError, NotFoundError

ADMIN = "root@example.com"
CT_OPEN = StateGuide(
    kind=StateKind.FAULT_CODE,
    code=3,
    label="CT_OPEN",
    severity=GuideSeverity.FAULT,
    message="A current transformer is open",
    probable_causes=("loose CT terminal",),
    checks=("Check the CT wiring at the meter",),
    safety_note="Never open a loaded CT secondary",
)
FAULT_GUIDE = GuideContent(meaning="Meter fault code", states=(CT_OPEN,))


class Setup:
    """Site 50 onboarded (meter M1: Power, Status, Fault); its knowledge service and the AI's
    store. `rename_m1` / `remove_m2` approve backend-ot changes."""

    def __init__(self, with_m2: bool = False) -> None:
        self.profile_store = InMemorySiteProfileStore.onboarded([mesa(with_m2=with_m2)], FIXED_NOW)
        self.authoring = InMemoryKnowledgeAuthoringStore()
        self._use(mesa(with_m2=with_m2))

    def _use(self, site_now: FakeSite) -> None:
        self.profiles = SiteProfileService(
            self.profile_store,
            backend(site_now),
            fixed_clock,
            cache_ttl_s=0,
        )
        self.knowledge = SiteKnowledgeService(
            self.authoring, self.profiles, fixed_clock, cache_ttl_s=0
        )
        self.ai = PublishedKnowledgeStore(self.knowledge, self.profiles)

    async def approve_backend(self, m1_name: str = "M1", with_m2: bool = False) -> None:
        self._use(mesa(m1_name=m1_name, with_m2=with_m2))
        await self.profiles.sync_site(SITE_ID)
        await self.profiles.approve(SITE_ID, ADMIN)


@pytest.fixture
def setup() -> Setup:
    return Setup()


class TestDraftAndPublish:
    async def test_the_ai_reads_only_what_is_published(self, setup: Setup) -> None:
        state = await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN, 0)
        assert state.draft_revision == 1 and [c.kind for c in state.changes] == ["added"]
        assert await setup.ai.get_point_guide(SITE_ID, 1, "M1.Fault") is None

        version = await setup.knowledge.publish(SITE_ID, ADMIN, draft_revision=1)
        assert (version.version, version.change_ids) == (1, ("point:1:Fault",))
        guide = await setup.ai.get_point_guide(SITE_ID, 1, "M1.Fault")
        assert guide is not None and guide.find_state(code=3) == CT_OPEN
        assert guide.point_name == "M1.Fault"  # named as the tools name points
        assert (await setup.knowledge.state(SITE_ID)).draft is None

    async def test_an_edit_or_publish_against_an_older_revision_is_refused(
        self, setup: Setup
    ) -> None:
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN, 0)
        with pytest.raises(ConflictError):  # loaded before the first edit
            await setup.knowledge.put_point_guide(
                SITE_ID, 1, "Status", GuideContent(meaning="x"), ADMIN, 0
            )
        await setup.knowledge.put_point_guide(
            SITE_ID, 1, "Status", GuideContent(meaning="On/off"), ADMIN, 1
        )
        with pytest.raises(ConflictError):  # reviewed at revision 1, edited since
            await setup.knowledge.publish(SITE_ID, ADMIN, draft_revision=1)
        assert (await setup.knowledge.publish(SITE_ID, ADMIN, draft_revision=2)).version == 1

    async def test_nothing_to_publish_without_changes(self, setup: Setup) -> None:
        with pytest.raises(InvalidRequestError, match="nothing to publish"):
            await setup.knowledge.publish(SITE_ID, ADMIN)

    async def test_the_next_publish_carries_the_whole_draft(self, setup: Setup) -> None:
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN)
        await setup.knowledge.publish(SITE_ID, ADMIN)
        state, document_id = await setup.knowledge.create_document(
            SITE_ID,
            DocumentContent(
                kind=KnowledgeKind.PROCEDURE, title="Meter reset", body="Press reset", device_id=1
            ),
            ADMIN,
        )
        await setup.knowledge.put_device_facts(
            SITE_ID,
            1,
            [DeviceRating(name="CT ratio", value=400, unit="A/5A")],
            "Spare CT in store",
            ADMIN,
        )
        await setup.knowledge.delete_point_guide(SITE_ID, 1, "Fault", ADMIN)
        changes = (await setup.knowledge.state(SITE_ID)).changes
        assert sorted((c.item_key, c.kind) for c in changes) == sorted(
            [
                ("point:1:Fault", "removed"),
                (f"document:{document_id}", "added"),
                ("device:1", "added"),
            ]
        )
        version = await setup.knowledge.publish(SITE_ID, ADMIN)
        assert version.version == 2 and len(version.change_ids) == 3
        assert await setup.ai.get_point_guide(SITE_ID, 1, "M1.Fault") is None
        assert [d.title for d in await setup.ai.list_documents(SITE_ID)] == ["Meter reset"]
        text = render_knowledge(
            await setup.ai.list_documents(SITE_ID), await setup.ai.list_device_facts(SITE_ID)
        )
        assert "- CT ratio: 400 A/5A" in text and "## Procedures" in text

    async def test_a_draft_back_at_the_published_content_goes_away(self, setup: Setup) -> None:
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN)
        state = await setup.knowledge.delete_point_guide(SITE_ID, 1, "Fault", ADMIN)
        assert state.draft is None and state.changes == ()


class TestValidation:
    async def test_only_approved_points_and_devices(self, setup: Setup) -> None:
        with pytest.raises(InvalidRequestError, match="no approved point"):
            await setup.knowledge.put_point_guide(SITE_ID, 1, "Nope", FAULT_GUIDE, ADMIN)
        with pytest.raises(InvalidRequestError, match="not in the approved profile"):
            await setup.knowledge.put_device_facts(SITE_ID, 2, [], None, ADMIN)  # M2 isn't approved
        with pytest.raises(NotFoundError, match="not onboarded"):
            await setup.knowledge.put_point_guide(99, 1, "Fault", FAULT_GUIDE, ADMIN)

    @pytest.mark.parametrize(
        "text",
        ["Reset with password: hunter2", "Meter at 10.20.30.40", "-----BEGIN RSA PRIVATE KEY-----"],
        ids=["credential", "ip-address", "private-key"],
    )
    async def test_secrets_and_addresses_are_refused(self, setup: Setup, text: str) -> None:
        with pytest.raises(InvalidRequestError, match="never stores"):
            await setup.knowledge.create_document(
                SITE_ID,
                DocumentContent(kind=KnowledgeKind.MANUAL, title="Manual", body=text),
                ADMIN,
            )

    async def test_a_version_number_is_not_an_ip_address(self, setup: Setup) -> None:
        await setup.knowledge.create_document(
            SITE_ID,
            DocumentContent(
                kind=KnowledgeKind.MANUAL, title="FW", body="Needs firmware 2.1.4 or 10.2"
            ),
            ADMIN,
        )

    async def test_one_entry_per_code_and_a_sane_range(self, setup: Setup) -> None:
        with pytest.raises(InvalidRequestError, match="two entries"):
            await setup.knowledge.put_point_guide(
                SITE_ID, 1, "Fault", GuideContent(meaning="x", states=(CT_OPEN, CT_OPEN)), ADMIN
            )
        limit = LimitGuide(
            condition=LimitCondition.ABOVE,
            value=600,
            severity=GuideSeverity.WARNING,
            message="Overload",
        )
        await setup.knowledge.put_point_guide(
            SITE_ID, 1, "Power", GuideContent(meaning="kW", limits=(limit,)), ADMIN
        )


class TestProfileChanges:
    async def test_an_approved_rename_keeps_the_guide_under_the_new_name(
        self, setup: Setup
    ) -> None:
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN)
        await setup.knowledge.publish(SITE_ID, ADMIN)
        await setup.approve_backend(m1_name="Meter1")
        assert await setup.ai.get_point_guide(SITE_ID, 1, "Meter1.Fault") is not None
        assert await setup.ai.get_point_guide(SITE_ID, 1, "M1.Fault") is None

    async def test_knowledge_of_a_removed_device_is_kept_but_not_served(self) -> None:
        setup = Setup(with_m2=True)
        await setup.knowledge.put_point_guide(SITE_ID, 2, "Fault", FAULT_GUIDE, ADMIN)
        await setup.knowledge.put_device_facts(SITE_ID, 2, [], "M2 is the spare", ADMIN)
        await setup.knowledge.publish(SITE_ID, ADMIN)
        assert await setup.ai.list_point_guides(SITE_ID)
        await setup.approve_backend()  # M2 removed in backend-ot, approved
        assert await setup.ai.list_point_guides(SITE_ID) == []
        assert await setup.ai.list_device_facts(SITE_ID) == []
        coverage = await setup.knowledge.coverage(SITE_ID)
        assert set(coverage.orphaned) == {"point:2:Fault", "device:2"}


class TestRevertAndRestore:
    async def test_revert_puts_single_changes_back(self, setup: Setup) -> None:
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN)
        await setup.knowledge.publish(SITE_ID, ADMIN)
        await setup.knowledge.put_point_guide(
            SITE_ID, 1, "Fault", GuideContent(meaning="wrong edit"), ADMIN
        )
        await setup.knowledge.put_point_guide(
            SITE_ID, 1, "Status", GuideContent(meaning="On/off"), ADMIN
        )
        state = await setup.knowledge.revert(SITE_ID, ["point:1:Fault"], ADMIN)
        assert [c.item_key for c in state.changes] == ["point:1:Status"]
        with pytest.raises(InvalidRequestError, match="not changed"):
            await setup.knowledge.revert(SITE_ID, ["point:1:Fault"], ADMIN)

    async def test_restore_publishes_an_old_version_again(self, setup: Setup) -> None:
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN)
        await setup.knowledge.publish(SITE_ID, ADMIN)
        await setup.knowledge.put_point_guide(
            SITE_ID, 1, "Fault", GuideContent(meaning="worse"), ADMIN
        )
        await setup.knowledge.publish(SITE_ID, ADMIN)
        await setup.knowledge.put_point_guide(
            SITE_ID, 1, "Status", GuideContent(meaning="x"), ADMIN
        )
        with pytest.raises(ConflictError, match="draft"):
            await setup.knowledge.restore(SITE_ID, 1, ADMIN)
        await setup.knowledge.discard_draft(SITE_ID)
        restored = await setup.knowledge.restore(SITE_ID, 1, ADMIN)
        assert (restored.version, restored.restored_from) == (3, 1)
        guide = await setup.ai.get_point_guide(SITE_ID, 1, "M1.Fault")
        assert guide is not None and guide.meaning == "Meter fault code"
        with pytest.raises(InvalidRequestError, match="already"):
            await setup.knowledge.restore(SITE_ID, 3, ADMIN)


class TestImportAndCoverage:
    async def test_an_export_imports_as_a_draft_checked_like_edits(self, setup: Setup) -> None:
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN)
        await setup.knowledge.publish(SITE_ID, ADMIN)
        exported = (await setup.knowledge.state(SITE_ID)).working
        other = Setup()
        state = await other.knowledge.import_content(SITE_ID, exported, "ana@example.com")
        assert [c.item_key for c in state.changes] == ["point:1:Fault"]
        assert state.working.point_guides[0].author == "ana@example.com"
        bad = exported.model_copy(
            update={
                "point_guides": (
                    exported.point_guides[0].model_copy(update={"point_name": "Gone"}),
                )
            }
        )
        with pytest.raises(InvalidRequestError):
            await other.knowledge.import_content(SITE_ID, bad, ADMIN)
        assert SiteKnowledge.model_validate_json(exported.model_dump_json()) == exported

    async def test_coverage_lists_status_and_alarm_points_without_a_guide(
        self, setup: Setup
    ) -> None:
        before = await setup.knowledge.coverage(SITE_ID)
        assert (before.points, before.discrete_points, before.discrete_with_guide) == (3, 2, 0)
        assert [(m.qualified_name, m.reason) for m in before.missing_guides] == [
            ("M1.Fault", "alarm"),
            ("M1.Status", "states"),
        ]
        await setup.knowledge.put_point_guide(SITE_ID, 1, "Fault", FAULT_GUIDE, ADMIN)
        after = await setup.knowledge.coverage(SITE_ID)  # counts the draft
        assert after.discrete_with_guide == 1 and after.devices_with_facts == 0
