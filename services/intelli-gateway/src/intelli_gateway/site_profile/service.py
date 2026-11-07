"""SiteProfileService: keeps each site's approved profile and backend-ot's latest catalog, lists
the differences, and applies the ones a site admin approves (docs/KNOWLEDGE_PLAN.md, section 2).

A sync only reads backend-ot and stores what it found; it never changes an approved profile. The
AI reads approved facts through site_profile/gate.py, which asks this service for a site's view.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.interfaces.site_profile_store import SiteProfileStore
from intelli_gateway.schemas.site_data import Site
from intelli_gateway.schemas.site_profile import (
    CatalogSnapshot,
    PendingChanges,
    ProfileVersion,
    SiteCatalog,
    SiteProfileStatus,
)
from intelli_gateway.site_profile.diff import (
    apply_changes,
    diff_catalogs,
    points_with_pending_changes,
)
from intelli_gateway.utils.exceptions import (
    ConflictError,
    GatewayError,
    InvalidRequestError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovedView:
    """What the AI may see of one site: the approved catalog, and which approved points have a
    definition change waiting for approval."""

    catalog: SiteCatalog
    pending_points: frozenset[str]
    loaded_at: datetime

    @property
    def point_names(self) -> frozenset[str]:
        return frozenset(point.name for point in self.catalog.points)

    @property
    def device_ids(self) -> frozenset[int]:
        return frozenset(device.device_id for device in self.catalog.devices)


class SiteProfileService:
    def __init__(
        self,
        store: SiteProfileStore,
        source: SiteDataConnector,
        clock: Callable[[], datetime],
        cache_ttl_s: float = 30,
    ) -> None:
        """`source` reads backend-ot's catalog (never the gated connector)."""
        self._store = store
        self._source = source
        self._clock = clock
        self._cache_ttl = timedelta(seconds=cache_ttl_s)
        self._views: dict[int, ApprovedView] = {}

    # --- reading backend-ot ---

    async def fetch_catalog(self, site_id: int) -> SiteCatalog | None:
        """backend-ot's current facts for the site; None when backend-ot has no such site."""
        site = await self._source.get_site(site_id)
        if site is None:
            return None
        devices, points, topology = await asyncio.gather(
            self._source.list_devices(site_id),
            self._source.list_points(site_id),
            self._source.get_topology(site_id),
        )
        return SiteCatalog(
            site=site,
            devices=tuple(sorted(devices, key=lambda device: device.device_id)),
            points=tuple(sorted(points, key=lambda point: point.name)),
            topology=topology,
        )

    async def sync_site(self, site_id: int) -> PendingChanges:
        """Read backend-ot now, store what it has, and return the pending changes."""
        catalog = await self.fetch_catalog(site_id)
        if catalog is None:
            raise NotFoundError("backend-ot has no such site")
        await self._store.save_snapshot(
            CatalogSnapshot(site_id=site_id, catalog=catalog, fetched_at=self._clock())
        )
        self._views.pop(site_id, None)
        return await self.pending_changes(site_id)

    async def sync_all(self) -> list[SiteProfileStatus]:
        """Sync every site backend-ot has. One site failing doesn't stop the others."""
        sites = await self._source.list_sites()
        for site in sites:
            try:
                await self.sync_site(site.site_id)
            except GatewayError as error:
                logger.warning(
                    "site_profile_sync_failed",
                    extra={"fields": {"site_id": site.site_id, "error": str(error)}},
                )
        logger.info("site_profile_sync_run", extra={"fields": {"sites": len(sites)}})
        return await self.statuses()

    # --- the admin's view ---

    async def statuses(self) -> list[SiteProfileStatus]:
        """Every site that was synced or onboarded, with its approved version and pending count."""
        profiles = {profile.site_id: profile for profile in await self._store.list_profiles()}
        snapshots = {snapshot.site_id: snapshot for snapshot in await self._store.list_snapshots()}
        statuses: list[SiteProfileStatus] = []
        for site_id in sorted(profiles.keys() | snapshots.keys()):
            profile, snapshot = profiles.get(site_id), snapshots.get(site_id)
            approved = profile.catalog if profile is not None else None
            latest = snapshot.catalog if snapshot is not None else approved
            if latest is None:
                continue
            pending = len(diff_catalogs(approved, snapshot.catalog)) if snapshot else 0
            statuses.append(
                SiteProfileStatus(
                    site_id=site_id,
                    name=latest.site.name,
                    approved_version=profile.version if profile else None,
                    approved_at=profile.approved_at if profile else None,
                    fetched_at=snapshot.fetched_at if snapshot else None,
                    pending_changes=pending,
                )
            )
        return statuses

    async def get_profile(self, site_id: int) -> ProfileVersion:
        profile = await self._store.get_profile(site_id)
        if profile is None:
            raise NotFoundError("site not onboarded: no approved profile")
        return profile

    async def versions(self, site_id: int) -> list[ProfileVersion]:
        versions = await self._store.list_versions(site_id)
        if not versions:
            raise NotFoundError("site not onboarded: no approved profile")
        return versions

    async def pending_changes(self, site_id: int) -> PendingChanges:
        snapshot = await self._store.get_snapshot(site_id)
        if snapshot is None:
            raise NotFoundError("site not synced from backend-ot yet")
        profile = await self._store.get_profile(site_id)
        return PendingChanges(
            site_id=site_id,
            fetched_at=snapshot.fetched_at,
            approved_version=profile.version if profile else None,
            changes=tuple(diff_catalogs(profile.catalog if profile else None, snapshot.catalog)),
        )

    async def approve(
        self,
        site_id: int,
        approved_by: str,
        change_ids: Sequence[str] | None = None,
        expected_fetched_at: datetime | None = None,
    ) -> ProfileVersion:
        """Approve pending changes (all of them when change_ids is None) into a new version.

        expected_fetched_at: the fetch the admin reviewed; a ConflictError when a newer sync
        replaced it, so nobody approves changes they haven't seen."""
        snapshot = await self._store.get_snapshot(site_id)
        if snapshot is None:
            raise NotFoundError("site not synced from backend-ot yet")
        if expected_fetched_at is not None and snapshot.fetched_at != expected_fetched_at:
            raise ConflictError("backend-ot was read again since; review the changes again")
        profile = await self._store.get_profile(site_id)
        approved = profile.catalog if profile else None
        pending = [change.change_id for change in diff_catalogs(approved, snapshot.catalog)]
        chosen = list(dict.fromkeys(pending if change_ids is None else change_ids))
        if not chosen:
            raise InvalidRequestError("no changes to approve")
        version = ProfileVersion(
            site_id=site_id,
            version=(profile.version + 1) if profile else 1,
            catalog=apply_changes(approved, snapshot.catalog, chosen),
            approved_at=self._clock(),
            approved_by=approved_by,
            change_ids=tuple(chosen),
        )
        await self._store.add_version(version)
        self._views.pop(site_id, None)
        logger.info(
            "site_profile_approved",
            extra={
                "fields": {
                    "site_id": site_id,
                    "version": version.version,
                    "changes": len(chosen),
                    "approved_by": approved_by,
                }
            },
        )
        return version

    # --- the AI's view (site_profile/gate.py) ---

    async def approved_view(self, site_id: int) -> ApprovedView | None:
        """The site as approved, or None when it isn't onboarded. Cached for a short TTL (and
        dropped at once by this instance's own sync or approval)."""
        now = self._clock()
        cached = self._views.get(site_id)
        if cached is not None and now - cached.loaded_at < self._cache_ttl:
            return cached
        profile = await self._store.get_profile(site_id)
        if profile is None:
            return None  # not cached: an onboarding shows at once
        snapshot = await self._store.get_snapshot(site_id)
        pending = (
            points_with_pending_changes(profile.catalog, snapshot.catalog)
            if snapshot
            else frozenset[str]()
        )
        view = ApprovedView(catalog=profile.catalog, pending_points=pending, loaded_at=now)
        self._views[site_id] = view
        return view

    async def approved_sites(self) -> list[Site]:
        return [profile.catalog.site for profile in await self._store.list_profiles()]
