"""ApprovedSiteDataConnector: the AI's only way to site data. It answers from a site's approved
profile and passes live reads to backend-ot only for approved devices and points.

- A site without an approved profile does not exist for the AI.
- Devices, points and topology come from the approved profile, not from backend-ot's current
  catalog: a device added in backend-ot stays invisible until a site admin approves it.
- Live values, history, alarms and comms are read through the wrapped connector, then cut down
  to approved devices and points. Points keep their approved names (a device rename waiting for
  approval doesn't rename them), and a value whose definition changed in backend-ot is flagged
  `definition_pending_review`.
"""

from collections.abc import Sequence
from datetime import datetime

from intelli_gateway.interfaces.site_data import SiteDataConnector
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
from intelli_gateway.site_profile.diff import point_key
from intelli_gateway.site_profile.service import ApprovedView, SiteProfileService


class ApprovedSiteDataConnector:
    def __init__(self, inner: SiteDataConnector, profiles: SiteProfileService) -> None:
        self._inner = inner
        self._profiles = profiles

    # --- facts: from the approved profile ---

    async def list_sites(self) -> list[Site]:
        return await self._profiles.approved_sites()

    async def get_site(self, site_id: int) -> Site | None:
        view = await self._profiles.approved_view(site_id)
        return view.catalog.site if view else None

    async def list_devices(self, site_id: int) -> list[Device]:
        view = await self._profiles.approved_view(site_id)
        return list(view.catalog.devices) if view else []

    async def get_topology(self, site_id: int) -> Topology:
        view = await self._profiles.approved_view(site_id)
        return view.catalog.topology if view else Topology()

    async def list_points(self, site_id: int) -> list[PointInfo]:
        view = await self._profiles.approved_view(site_id)
        return list(view.catalog.points) if view else []

    # --- live data: approved devices and points only ---

    async def get_latest_many(
        self, site_id: int, point_names: Sequence[str]
    ) -> dict[str, PointValue | None]:
        result: dict[str, PointValue | None] = dict.fromkeys(point_names)
        view = await self._profiles.approved_view(site_id)
        if view is None:
            return result
        live_names = await self._live_names(site_id, view)
        wanted = {name: live_names[name] for name in point_names if name in live_names}
        latest = await self._inner.get_latest_many(site_id, list(wanted.values()))
        for name, live_name in wanted.items():
            value = latest.get(live_name)
            if value is not None:
                result[name] = value.model_copy(
                    update={
                        "name": name,
                        "definition_pending_review": name in view.pending_points,
                    }
                )
        return result

    async def get_history(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[HistorySample] | None:
        live_name = await self._live_name(site_id, point_name)
        if live_name is None:
            return None
        return await self._inner.get_history(site_id, live_name, start, end)

    async def get_state_changes(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[StateChange] | None:
        live_name = await self._live_name(site_id, point_name)
        if live_name is None:
            return None
        return await self._inner.get_state_changes(site_id, live_name, start, end)

    async def get_active_alarms(self, site_id: int) -> ActiveAlarms:
        view = await self._profiles.approved_view(site_id)
        if view is None:
            return ActiveAlarms(events=[], point_alarms=[])
        active = await self._inner.get_active_alarms(site_id)
        approved_names = {
            live: approved for approved, live in (await self._live_names(site_id, view)).items()
        }
        return ActiveAlarms(
            events=[event for event in active.events if self._device_ok(view, event.device_id)],
            point_alarms=[
                alarm.model_copy(update={"point_name": approved_names[alarm.point_name]})
                for alarm in active.point_alarms
                if alarm.point_name in approved_names
            ],
        )

    async def get_alarm_events(
        self, site_id: int, start: datetime, end: datetime, device_id: int | None = None
    ) -> list[AlarmEvent]:
        view = await self._profiles.approved_view(site_id)
        if view is None or (device_id is not None and device_id not in view.device_ids):
            return []
        events = await self._inner.get_alarm_events(site_id, start, end, device_id)
        return [event for event in events if self._device_ok(view, event.device_id)]

    async def get_device_comms(self, site_id: int) -> list[DeviceComms]:
        view = await self._profiles.approved_view(site_id)
        if view is None:
            return []
        comms = await self._inner.get_device_comms(site_id)
        return [entry for entry in comms if entry.device_id in view.device_ids]

    async def aclose(self) -> None:
        await self._inner.aclose()

    # --- helpers ---

    @staticmethod
    def _device_ok(view: ApprovedView, device_id: int | None) -> bool:
        """Site-level events (no device) and approved devices' events."""
        return device_id is None or device_id in view.device_ids

    async def _live_names(self, site_id: int, view: ApprovedView) -> dict[str, str]:
        """Approved point name -> the name the wrapped connector knows it by now. A point that
        backend-ot no longer has is left out (no live data for it)."""
        live = {point_key(point): point.name for point in await self._inner.list_points(site_id)}
        return {
            point.name: live[point_key(point)]
            for point in view.catalog.points
            if point_key(point) in live
        }

    async def _live_name(self, site_id: int, point_name: str) -> str | None:
        view = await self._profiles.approved_view(site_id)
        if view is None or point_name not in view.point_names:
            return None
        return (await self._live_names(site_id, view)).get(point_name)
