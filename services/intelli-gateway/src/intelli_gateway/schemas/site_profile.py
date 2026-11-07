"""Site profile: the gateway's approved copy of a site's facts (site, devices, points, topology),
taken from backend-ot. The AI sees only an approved profile. backend-ot changes wait as pending
changes until a site admin approves them (docs/KNOWLEDGE_PLAN.md, section 2).

Nothing about the network or polling is copied: the shapes below (schemas/site_data.py) have no
host, port, Modbus address or scan setting.
"""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict

from intelli_gateway.schemas.site_data import Device, PointInfo, Site, Topology


class SiteCatalog(BaseModel):
    """A site's facts at one moment: what was fetched from backend-ot, or what was approved."""

    model_config = ConfigDict(frozen=True)

    site: Site
    devices: tuple[Device, ...] = ()
    points: tuple[PointInfo, ...] = ()
    topology: Topology = Topology()


class CatalogSnapshot(BaseModel):
    """The latest catalog fetched from backend-ot for a site (one per site, replaced each sync)."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    catalog: SiteCatalog
    fetched_at: AwareDatetime


class ProfileVersion(BaseModel):
    """One approved version of a site's profile. The highest version is the one the AI uses."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    version: int
    catalog: SiteCatalog
    approved_at: AwareDatetime
    approved_by: str
    # The pending changes this version approved (change ids, see ProfileChange).
    change_ids: tuple[str, ...] = ()


class ChangeTarget(StrEnum):
    SITE = "site"
    DEVICE = "device"
    POINT = "point"
    TOPOLOGY = "topology"


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


class ProfileChange(BaseModel):
    """One difference between the approved profile and backend-ot's current catalog.

    change_id is stable for the same difference: `site`, `topology`, `device:<device_id>`,
    `point:<device_id>:<point name in its device>`. A device added or removed carries its points
    (they are not listed separately)."""

    model_config = ConfigDict(frozen=True)

    change_id: str
    target: ChangeTarget
    kind: ChangeKind
    summary: str
    device_id: int | None = None
    # The point's name within its device (backend-ot's name, without the device prefix).
    point_name: str | None = None
    # CHANGED only: the fields that differ.
    fields: tuple[str, ...] = ()


class PendingChanges(BaseModel):
    model_config = ConfigDict(frozen=True)

    site_id: int
    # When backend-ot was last read for this site.
    fetched_at: AwareDatetime
    approved_version: int | None
    changes: tuple[ProfileChange, ...]


class SiteProfileStatus(BaseModel):
    """One site as the admin sees it: onboarded or not, and how many changes wait."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    name: str
    approved_version: int | None = None
    approved_at: AwareDatetime | None = None
    fetched_at: AwareDatetime | None = None
    pending_changes: int = 0
