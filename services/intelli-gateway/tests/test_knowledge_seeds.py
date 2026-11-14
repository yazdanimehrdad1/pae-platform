"""The code-level knowledge seed for powerflow's 2bess_1pv site (`manage_knowledge seed`).

Invariant guarded:
- the seed passes the same checks as the admin UI against the site's approved profile (only
  approved devices, points and functions; no secrets) and publishes in one version
- its site prompts cover every kind of link: none, points only, documents only, and points,
  documents, functions and device ratings together; every link resolves
- device ids come from the approved profile by device name, so the seed fits any database
- seeding again changes nothing; it finds the site by name, and refuses a site without these
  devices
"""

from argparse import Namespace

import pytest
from doubles.knowledge_authoring_store import InMemoryKnowledgeAuthoringStore
from doubles.site_profile_store import InMemorySiteProfileStore
from fakes import FIXED_NOW, fixed_clock
from site_profile_fakes import backend, mesa

from intelli_gateway.knowledge.seeds import SEEDS
from intelli_gateway.knowledge.seeds.powerflow_2bess_1pv import (
    SITE_NAME,
    powerflow_2bess_1pv_knowledge,
)
from intelli_gateway.knowledge.service import SiteKnowledgeService
from intelli_gateway.manage_knowledge import _seed  # pyright: ignore[reportPrivateUsage]
from intelli_gateway.schemas.site_data import Device, PointInfo, Site, SiteFunction
from intelli_gateway.schemas.site_profile import ProfileVersion, SiteCatalog
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.utils.exceptions import InvalidRequestError

SITE = 1002
ADMIN = "admin@example.com"
# Ids as another database might number them (the seed must not assume the dev stack's).
DEVICE_IDS = {
    "plant_controller": 40,
    "bess1": 41,
    "bess2": 42,
    "pv1": 43,
    "poi_meter": 45,
}
POINTS = {
    "plant_controller": ("Alrm", "GridMode"),
    "bess1": ("InvSt", "SoC", "Evt1"),
    "bess2": ("InvSt", "SoC", "Evt1"),
    "pv1": ("InvSt", "ThrotSrc", "W", "WAvail"),
    "poi_meter": ("Hz",),
}
FUNCTIONS = (
    "site-assets-active-power",
    "site-bess1-round-trip-efficiency",
    "site-bess2-round-trip-efficiency",
)


def catalog(site_name: str = SITE_NAME, without: str | None = None) -> SiteCatalog:
    devices = [
        Device(device_id=device_id, name=f"2bess_1pv-{short}", type="BESS")
        for short, device_id in DEVICE_IDS.items()
        if short != without
    ]
    points = [
        PointInfo(
            name=f"2bess_1pv-{short}.{point}",
            device_id=DEVICE_IDS[short],
            device_name=f"2bess_1pv-{short}",
            equipment=short,
        )
        for short, names in POINTS.items()
        if short != without
        for point in names
    ]
    return SiteCatalog(
        site=Site(site_id=SITE, name=site_name),
        devices=tuple(devices),
        points=tuple(points),
        functions=tuple(SiteFunction(name=name, kind="site", summary=name) for name in FUNCTIONS),
    )


async def services(approved: SiteCatalog) -> tuple[SiteProfileService, SiteKnowledgeService]:
    store = InMemorySiteProfileStore()
    await store.add_version(
        ProfileVersion(
            site_id=SITE, version=1, catalog=approved, approved_at=FIXED_NOW, approved_by="tests"
        )
    )
    profiles = SiteProfileService(store, backend(mesa()), fixed_clock, cache_ttl_s=0)
    knowledge = SiteKnowledgeService(
        InMemoryKnowledgeAuthoringStore(), profiles, fixed_clock, cache_ttl_s=0
    )
    return profiles, knowledge


def seed_args(site: int | None = None, no_publish: bool = False) -> Namespace:
    return Namespace(name="powerflow_2bess_1pv", site=site, by=ADMIN, no_publish=no_publish)


class TestSeedContent:
    def test_registered_for_its_site(self) -> None:
        assert SEEDS["powerflow_2bess_1pv"].site_name == SITE_NAME

    def test_device_ids_come_from_the_profile(self) -> None:
        content = powerflow_2bess_1pv_knowledge(catalog())
        used = {guide.device_id for guide in content.point_guides}
        used |= {facts.device_id for facts in content.device_facts}
        assert used <= set(DEVICE_IDS.values())
        bess1_soc = next(
            guide
            for guide in content.point_guides
            if (guide.device_id, guide.point_name) == (DEVICE_IDS["bess1"], "SoC")
        )
        assert bess1_soc.normal_range is not None

    def test_prompts_cover_every_kind_of_link(self) -> None:
        prompts = powerflow_2bess_1pv_knowledge(catalog()).site_prompts
        shapes = {
            (
                bool(prompt.links.points),
                bool(prompt.links.documents),
                bool(prompt.links.devices),
                bool(prompt.links.functions),
            )
            for prompt in prompts
        }
        assert (False, False, False, False) in shapes  # no links
        assert (True, False, False, False) in shapes  # points only
        assert (False, True, False, False) in shapes  # documents only
        assert (True, True, True, True) in shapes  # points, documents, ratings, functions
        assert [prompt.position for prompt in prompts] == list(range(1, len(prompts) + 1))

    def test_refuses_a_site_without_its_devices(self) -> None:
        with pytest.raises(InvalidRequestError, match="2bess_1pv-pv1"):
            powerflow_2bess_1pv_knowledge(catalog(without="pv1"))


class TestSeedCommand:
    async def test_publishes_everything_through_the_authoring_checks(self) -> None:
        profiles, knowledge = await services(catalog())
        output = await _seed(seed_args(), profiles, knowledge)
        assert "published v1" in output
        state = await knowledge.state(SITE)
        assert state.draft is None and state.published is not None
        published = state.published.content
        assert len(published.site_prompts) == 5 and len(published.documents) == 4
        assert {facts.device_id for facts in published.device_facts} == {
            DEVICE_IDS[short] for short in ("plant_controller", "bess1", "bess2", "pv1")
        }
        assert all(item.author == ADMIN for item in published.point_guides)

    async def test_seeding_again_changes_nothing(self) -> None:
        profiles, knowledge = await services(catalog())
        await _seed(seed_args(), profiles, knowledge)
        output = await _seed(seed_args(), profiles, knowledge)
        assert "nothing changed" in output
        assert [version.version for version in await knowledge.versions(SITE)] == [1]
        assert (await knowledge.state(SITE)).draft is None  # no empty draft left to review

    async def test_no_publish_leaves_a_draft(self) -> None:
        profiles, knowledge = await services(catalog())
        await _seed(seed_args(no_publish=True), profiles, knowledge)
        state = await knowledge.state(SITE)
        assert state.published is None and state.draft is not None and state.changes

    async def test_needs_the_site_by_name_or_an_explicit_site(self) -> None:
        profiles, knowledge = await services(catalog(site_name="Somewhere else"))
        with pytest.raises(SystemExit, match="pass --site"):
            await _seed(seed_args(), profiles, knowledge)
        assert "published v1" in await _seed(seed_args(site=SITE), profiles, knowledge)
