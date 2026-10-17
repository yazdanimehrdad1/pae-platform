"""Site data interface: what backend-ot serves. Implementations: fake_data/site_data.py now,
services/backend_ot next. All access is read-only."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from intelli_gateway.schemas.site_data import (
    ActiveAlarms,
    AlarmEvent,
    Device,
    DeviceComms,
    HistorySample,
    PointInfo,
    PointValue,
    Site,
    StateChange,
    Topology,
)


class SiteDataConnector(Protocol):
    """Site data: what backend-ot serves."""

    async def list_sites(self) -> list[Site]: ...

    async def get_site(self, site_id: int) -> Site | None: ...

    async def list_devices(self, site_id: int) -> list[Device]: ...

    async def get_topology(self, site_id: int) -> Topology: ...

    async def list_points(self, site_id: int) -> list[PointInfo]: ...

    async def get_latest_many(
        self, site_id: int, point_names: Sequence[str]
    ) -> dict[str, PointValue | None]:
        """Latest value per name; None for names that are not points of this site."""
        ...

    async def get_history(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[HistorySample] | None:
        """Samples in [start, end], oldest first. None if the point does not exist."""
        ...

    async def get_state_changes(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[StateChange] | None:
        """For enum/bitfield points: the value at start, then every change. None if the point
        does not exist."""
        ...

    async def get_active_alarms(self, site_id: int) -> ActiveAlarms: ...

    async def get_alarm_events(
        self, site_id: int, start: datetime, end: datetime, device_id: int | None = None
    ) -> list[AlarmEvent]:
        """Alarm events active at any time in [start, end], oldest first."""
        ...

    async def get_device_comms(self, site_id: int) -> list[DeviceComms]: ...

    async def aclose(self) -> None: ...
