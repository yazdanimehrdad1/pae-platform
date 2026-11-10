"""InMemorySiteProfileStore: site profiles in process memory, for tests only. Same behavior as
the Postgres store (both pass tests/site_profile_store_contract.py)."""

from collections.abc import Sequence
from datetime import datetime

from doubles.models import FakeSite
from intelli_gateway.schemas.site_profile import CatalogSnapshot, ProfileVersion, SiteCatalog
from intelli_gateway.utils.exceptions import ConflictError


def catalog_of(fake: FakeSite) -> SiteCatalog:
    """A fictional site's catalog, as SiteProfileService.fetch_catalog builds it."""
    return SiteCatalog(
        site=fake.site,
        devices=tuple(sorted(fake.devices, key=lambda device: device.device_id)),
        points=tuple(sorted((point.info for point in fake.points), key=lambda info: info.name)),
        topology=fake.topology,
    )


class InMemorySiteProfileStore:
    def __init__(self) -> None:
        self._versions: dict[int, dict[int, ProfileVersion]] = {}
        self._snapshots: dict[int, CatalogSnapshot] = {}

    @classmethod
    def onboarded(
        cls, sites: Sequence[FakeSite], approved_at: datetime
    ) -> "InMemorySiteProfileStore":
        """A store where these fictional sites are already onboarded, everything approved."""
        store = cls()
        for fake in sites:
            store._versions[fake.site.site_id] = {
                1: ProfileVersion(
                    site_id=fake.site.site_id,
                    version=1,
                    catalog=catalog_of(fake),
                    approved_at=approved_at,
                    approved_by="tests",
                )
            }
        return store

    async def get_profile(self, site_id: int) -> ProfileVersion | None:
        versions = self._versions.get(site_id)
        return versions[max(versions)] if versions else None

    async def list_profiles(self) -> list[ProfileVersion]:
        return [
            versions[max(versions)] for _, versions in sorted(self._versions.items()) if versions
        ]

    async def list_versions(self, site_id: int) -> list[ProfileVersion]:
        versions = self._versions.get(site_id, {})
        return [versions[number] for number in sorted(versions, reverse=True)]

    async def add_version(self, profile: ProfileVersion) -> None:
        versions = self._versions.setdefault(profile.site_id, {})
        if profile.version in versions:
            raise ConflictError(
                f"site {profile.site_id} already has profile version {profile.version}"
            )
        versions[profile.version] = profile

    async def get_snapshot(self, site_id: int) -> CatalogSnapshot | None:
        return self._snapshots.get(site_id)

    async def list_snapshots(self) -> list[CatalogSnapshot]:
        return [self._snapshots[site_id] for site_id in sorted(self._snapshots)]

    async def save_snapshot(self, snapshot: CatalogSnapshot) -> None:
        self._snapshots[snapshot.site_id] = snapshot
