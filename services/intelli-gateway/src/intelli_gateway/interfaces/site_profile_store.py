"""Where approved site profiles and the latest backend-ot catalogs are kept. Implementations:
Postgres (services/postgres/site_profile_store.py) and in memory in tests
(tests/doubles/site_profile_store.py), both checked by tests/site_profile_store_contract.py."""

from typing import Protocol

from intelli_gateway.schemas.site_profile import CatalogSnapshot, ProfileVersion


class SiteProfileStore(Protocol):
    async def get_profile(self, site_id: int) -> ProfileVersion | None:
        """The site's latest approved version; None when the site was never onboarded."""
        ...

    async def list_profiles(self) -> list[ProfileVersion]:
        """The latest approved version of every onboarded site, by site_id."""
        ...

    async def list_versions(self, site_id: int) -> list[ProfileVersion]:
        """Every approved version of the site, newest first."""
        ...

    async def add_version(self, profile: ProfileVersion) -> None:
        """Store a new version. ConflictError when that version number already exists (another
        approval got there first)."""
        ...

    async def get_snapshot(self, site_id: int) -> CatalogSnapshot | None: ...

    async def list_snapshots(self) -> list[CatalogSnapshot]:
        """The latest fetched catalog of every site, by site_id."""
        ...

    async def save_snapshot(self, snapshot: CatalogSnapshot) -> None:
        """Replace the site's latest fetched catalog."""
        ...
