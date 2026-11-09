"""The SiteProfileStore contract, shared by the in-memory fake (unit tests) and Postgres
(tests/integration): every implementation must pass these checks unchanged."""

from datetime import UTC, datetime, timedelta

import pytest

from intelli_gateway.interfaces.site_profile_store import SiteProfileStore
from intelli_gateway.schemas.site_data import (
    Device,
    PointClass,
    PointInfo,
    Site,
    SiteFunction,
    SiteFunctionParameter,
    Topology,
    TopologyConnection,
    TopologyNode,
)
from intelli_gateway.schemas.site_profile import CatalogSnapshot, ProfileVersion, SiteCatalog
from intelli_gateway.utils.exceptions import ConflictError

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def catalog(site_id: int = 1, name: str = "Mesa", unit: str = "kW") -> SiteCatalog:
    return SiteCatalog(
        site=Site(site_id=site_id, name=name, timezone="America/Phoenix", capacity_kw=500),
        devices=(Device(device_id=1, name="M1", type="METER", vendor="Acme"),),
        points=(
            PointInfo(
                name="M1.Power",
                unit=unit,
                device_id=1,
                device_name="M1",
                equipment="meter",
                point_class=PointClass.ANALOG,
            ),
            PointInfo(
                name="M1.Status",
                device_id=1,
                device_name="M1",
                equipment="meter",
                data_type="enum16",
                enum_labels={0: "off", 1: "on"},
                bit_labels={},
            ),
        ),
        topology=Topology(
            nodes=(TopologyNode(node_id="m1", type="meter", name="M1", device_id=1),),
            connections=(TopologyConnection(from_id="m1", to_id="poi"),),
        ),
        functions=(
            SiteFunction(
                name="device-meter-check",
                kind="device",
                summary="Meter data completeness (%)",
                device_types=("METER",),
                parameters=(
                    SiteFunctionParameter(
                        name="lookback_days", type="integer", default=7, minimum=1.0
                    ),
                ),
            ),
        ),
    )


def version(site_id: int, number: int, **catalog_args: str) -> ProfileVersion:
    return ProfileVersion(
        site_id=site_id,
        version=number,
        catalog=catalog(site_id, **catalog_args),
        approved_at=NOW + timedelta(minutes=number),
        approved_by="admin@example.com",
        change_ids=("site", "device:1"),
    )


async def a_new_site_has_nothing(store: SiteProfileStore) -> None:
    assert await store.get_profile(1) is None
    assert await store.list_profiles() == []
    assert await store.list_versions(1) == []
    assert await store.get_snapshot(1) is None
    assert await store.list_snapshots() == []


async def versions_read_back_exactly(store: SiteProfileStore) -> None:
    first = version(1, 1)
    await store.add_version(first)
    assert await store.get_profile(1) == first  # enum labels keep their int keys
    second = version(1, 2, unit="W")
    await store.add_version(second)
    assert await store.get_profile(1) == second
    assert await store.list_versions(1) == [second, first]


async def the_latest_version_of_each_site_is_listed(store: SiteProfileStore) -> None:
    await store.add_version(version(2, 1))
    await store.add_version(version(1, 1))
    await store.add_version(version(1, 2, name="Mesa II"))
    listed = await store.list_profiles()
    assert [(profile.site_id, profile.version) for profile in listed] == [(1, 2), (2, 1)]
    assert listed[0].catalog.site.name == "Mesa II"


async def a_version_number_is_taken_once(store: SiteProfileStore) -> None:
    await store.add_version(version(1, 1))
    with pytest.raises(ConflictError):
        await store.add_version(version(1, 1, name="other"))
    profile = await store.get_profile(1)
    assert profile is not None and profile.catalog.site.name == "Mesa"


async def a_sync_replaces_the_sites_snapshot(store: SiteProfileStore) -> None:
    first = CatalogSnapshot(site_id=1, catalog=catalog(1), fetched_at=NOW)
    await store.save_snapshot(first)
    assert await store.get_snapshot(1) == first
    newer = CatalogSnapshot(
        site_id=1, catalog=catalog(1, unit="W"), fetched_at=NOW + timedelta(minutes=15)
    )
    await store.save_snapshot(newer)
    other = CatalogSnapshot(site_id=2, catalog=catalog(2), fetched_at=NOW)
    await store.save_snapshot(other)
    assert await store.get_snapshot(1) == newer
    assert await store.list_snapshots() == [newer, other]


CHECKS = [
    a_new_site_has_nothing,
    versions_read_back_exactly,
    the_latest_version_of_each_site_is_listed,
    a_version_number_is_taken_once,
    a_sync_replaces_the_sites_snapshot,
]
