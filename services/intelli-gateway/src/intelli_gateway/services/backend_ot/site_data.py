"""SiteDataConnector over backend-ot: maps backend-ot's responses onto the agent's site-data
shapes (schemas/site_data.py).

Point names: backend-ot names are only unique within a device, so the agent sees them qualified
as `DEVICE.point` (e.g. `INV2.active_power`). This module maps those names back to backend-ot's
device and point ids. The catalog (devices and their points) is cached per site for a short TTL.

Known gaps in backend-ot, handled here: points have no description, readings carry no quality,
and there is no poll history, so a device's last reading time stands in for comms health.
"""

import asyncio
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from intelli_gateway.schemas.backend_ot.responses import (
    AlarmDefinitionResponse,
    AlarmEventResponse,
    DevicePointResponse,
    DeviceWithPoints,
    SiteResponse,
    TimeseriesPoint,
    TranslatedValue,
)
from intelli_gateway.schemas.site_data import (
    ActiveAlarms,
    ActivePointAlarm,
    AlarmEvent,
    AlarmSeverity,
    Device,
    DeviceComms,
    HistorySample,
    PointClass,
    PointInfo,
    PointValue,
    Site,
    StateChange,
    Topology,
    TopologyConnection,
    TopologyNode,
)
from intelli_gateway.services.backend_ot.client import BackendOtClient

# Enough samples for a good summary of any window; backend-ot keeps extremes when it thins.
HISTORY_MAX_POINTS = 2000
_DISCRETE_TYPES = ("enum", "bitfield", "status_word", "bool")
_CAPACITY = re.compile(r"([-+]?\d+(?:[.,]\d+)?)\s*([kKmMgG]?)[wW]")


def qualified_name(device_name: str, point_name: str) -> str:
    return f"{device_name}.{point_name}"


def aware(moment: datetime) -> datetime:
    """backend-ot sends offsets; a naive timestamp is taken as UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def parse_capacity_kw(capacity: str) -> float | None:
    """backend-ot's capacity is free text ('5 MW', '2500 kW', '5'). Plain numbers are kW."""
    match = _CAPACITY.search(capacity)
    if match is None:
        try:
            return float(capacity.replace(",", "."))
        except ValueError:
            return None
    value = float(match.group(1).replace(",", "."))
    return value * {"k": 1, "m": 1_000, "g": 1_000_000, "": 0.001}[match.group(2).lower()]


def _int_keys(detail: dict[str, str] | None) -> dict[int, str]:
    labels: dict[int, str] = {}
    for key, label in (detail or {}).items():
        try:
            labels[int(key.removeprefix("bit-"))] = label
        except ValueError:
            continue
    return labels


def _is_discrete(point: DevicePointResponse) -> bool:
    return point.data_type.startswith(_DISCRETE_TYPES) or bool(
        point.enum_detail or point.bitfield_detail
    )


def _translated(value: TranslatedValue) -> tuple[str | None, list[str] | None]:
    """An enum label, or the labels of the set bits."""
    if isinstance(value, str):
        return value, None
    if isinstance(value, dict):
        return None, [label for label, state in value.items() if state]
    return None, None


@dataclass(frozen=True)
class _CatalogPoint:
    device: DeviceWithPoints
    point: DevicePointResponse
    info: PointInfo


@dataclass
class _Catalog:
    loaded_at: datetime
    devices: list[DeviceWithPoints]
    points: dict[str, _CatalogPoint]


class BackendOtSiteDataConnector:
    def __init__(
        self,
        client: BackendOtClient,
        stale_after_s: float,
        catalog_ttl_s: float = 60,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = client
        self._stale_after_s = stale_after_s
        self._catalog_ttl = timedelta(seconds=catalog_ttl_s)
        self._clock = clock
        self._catalogs: dict[int, _Catalog] = {}

    # --- sites, devices, topology, catalog ---

    async def list_sites(self) -> list[Site]:
        return [self._site(site) for site in await self._client.list_sites()]

    async def get_site(self, site_id: int) -> Site | None:
        site = await self._client.get_site(site_id)
        return self._site(site) if site else None

    async def list_devices(self, site_id: int) -> list[Device]:
        return [
            Device(
                device_id=device.device_id,
                name=device.name,
                type=device.type,
                vendor=device.vendor,
                model=device.model,
                description=device.description,
            )
            for device in (await self._catalog(site_id)).devices
        ]

    async def get_topology(self, site_id: int) -> Topology:
        response = await self._client.get_sld(site_id)
        if response is None:
            return Topology()
        sld = response.sld
        return Topology(
            nodes=tuple(
                TopologyNode(
                    node_id=node.id,
                    type=node.type,
                    name=node.name,
                    device_id=node.device.device_id if node.device else None,
                )
                for node in sld.nodes
            ),
            connections=tuple(
                TopologyConnection(from_id=link.from_id, to_id=link.to_id)
                for link in sld.connections
            ),
        )

    async def list_points(self, site_id: int) -> list[PointInfo]:
        return [entry.info for entry in (await self._catalog(site_id)).points.values()]

    # --- readings ---

    async def get_latest_many(
        self, site_id: int, point_names: Sequence[str]
    ) -> dict[str, PointValue | None]:
        catalog = await self._catalog(site_id)
        result: dict[str, PointValue | None] = dict.fromkeys(point_names)
        by_device: dict[int, list[_CatalogPoint]] = {}
        for name in point_names:
            entry = catalog.points.get(name)
            if entry is not None:
                by_device.setdefault(entry.device.device_id, []).append(entry)
        responses = await asyncio.gather(
            *(
                self._client.latest(site_id, device_id, [e.point.id for e in entries])
                for device_id, entries in by_device.items()
            )
        )
        now = self._clock()
        for entries, response in zip(by_device.values(), responses, strict=True):
            for entry in entries:
                reading = response.readings.get(str(entry.point.id))
                timestamp = aware(reading.time) if reading and reading.time else None
                age_s = (now - timestamp).total_seconds() if timestamp else None
                label, active_bits = _translated(reading.translated_value if reading else None)
                raw = reading.value if reading else None
                value: float | int | None = (
                    int(raw) if raw is not None and _is_discrete(entry.point) else raw
                )
                result[entry.info.name] = PointValue(
                    name=entry.info.name,
                    device_id=entry.device.device_id,
                    value=value,
                    unit=entry.point.unit,
                    timestamp=timestamp,
                    label=label,
                    active_bits=active_bits,
                    age_s=age_s,
                    stale=age_s is None or age_s > self._stale_after_s,
                )
        return result

    async def get_history(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[HistorySample] | None:
        entry = (await self._catalog(site_id)).points.get(point_name)
        if entry is None:
            return None
        series = await self._series(site_id, entry, start, end)
        return [
            HistorySample(timestamp=aware(sample.time), value=sample.value)
            for sample in series
            if sample.value is not None
        ]

    async def get_state_changes(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[StateChange] | None:
        entry = (await self._catalog(site_id)).points.get(point_name)
        if entry is None:
            return None
        changes: list[StateChange] = []
        previous: int | None = None
        for sample in await self._series(site_id, entry, start, end):
            if sample.value is None:
                continue
            code = int(sample.value)
            if code == previous:
                continue
            label, active_bits = _translated(sample.translated_value)
            changes.append(
                StateChange(
                    timestamp=aware(sample.time), value=code, label=label, active_bits=active_bits
                )
            )
            previous = code
        return changes

    # --- alarms and comms ---

    async def get_active_alarms(self, site_id: int) -> ActiveAlarms:
        snapshot, health = await asyncio.gather(
            self._client.alarm_snapshot(site_id), self._client.site_health(site_id)
        )
        names = {definition.id: definition for definition in snapshot.definitions}
        events = [
            self._event(event, names) for event in snapshot.events if event.cleared_at is None
        ]
        point_alarms = [
            ActivePointAlarm(
                point_name=qualified_name(device.device_name, alarm.device_point_name),
                device_id=device.device_id,
                severity=alarm.severity,
                value=alarm.value,
                label=alarm.enum_label,
                active_bits=alarm.active_bits or None,
                timestamp=aware(alarm.timestamp),
            )
            for device in health.devices
            for alarm in device.active_alarms
        ]
        return ActiveAlarms(events=events, point_alarms=point_alarms)

    async def get_alarm_events(
        self, site_id: int, start: datetime, end: datetime, device_id: int | None = None
    ) -> list[AlarmEvent]:
        events, snapshot = await asyncio.gather(
            self._client.alarm_events(site_id, start, end, device_id),
            self._client.alarm_snapshot(site_id),
        )
        names = {definition.id: definition for definition in snapshot.definitions}
        return sorted(
            (self._event(event, names) for event in events), key=lambda event: event.raised_at
        )

    async def get_device_comms(self, site_id: int) -> list[DeviceComms]:
        devices = (await self._catalog(site_id)).devices
        responses = await asyncio.gather(
            *(self._client.latest(site_id, device.device_id) for device in devices)
        )
        now = self._clock()
        comms: list[DeviceComms] = []
        for device, response in zip(devices, responses, strict=True):
            times = [aware(r.time) for r in response.readings.values() if r.time is not None]
            last = max(times) if times else None
            comms.append(
                DeviceComms(
                    device_id=device.device_id,
                    last_reading_at=last,
                    stale=last is None or (now - last).total_seconds() > self._stale_after_s,
                )
            )
        return comms

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- helpers ---

    async def _catalog(self, site_id: int) -> _Catalog:
        now = self._clock()
        cached = self._catalogs.get(site_id)
        if cached is not None and now - cached.loaded_at < self._catalog_ttl:
            return cached
        devices = await self._client.list_devices(site_id)
        points: dict[str, _CatalogPoint] = {}
        for device in devices:
            # Standardized points are empty placeholders in backend-ot; native and virtual
            # points carry the data.
            for point in [*device.points.native, *device.points.virtual]:
                name = qualified_name(device.name, point.name)
                points[name] = _CatalogPoint(
                    device=device,
                    point=point,
                    info=PointInfo(
                        name=name,
                        unit=point.unit,
                        device_id=device.device_id,
                        device_name=device.name,
                        equipment=device.type.lower(),
                        data_type=point.data_type,
                        point_class=PointClass(point.point_class) if point.point_class else None,
                        severity=point.severity,
                        enum_labels=_int_keys(point.enum_detail),
                        bit_labels=_int_keys(point.bitfield_detail),
                    ),
                )
        catalog = _Catalog(loaded_at=now, devices=devices, points=points)
        self._catalogs[site_id] = catalog
        return catalog

    async def _series(
        self, site_id: int, entry: _CatalogPoint, start: datetime, end: datetime
    ) -> list[TimeseriesPoint]:
        response = await self._client.timeseries(
            site_id, entry.device.device_id, [entry.point.id], start, end, HISTORY_MAX_POINTS
        )
        series = response.readings.get(str(entry.point.id))
        samples = list(series.timeseries) if series else []
        return sorted(samples, key=lambda sample: sample.time)

    @staticmethod
    def _site(site: SiteResponse) -> Site:
        return Site(
            site_id=site.site_id,
            name=site.name,
            description=site.description,
            capacity_kw=parse_capacity_kw(site.capacity),
            timezone=site.timezone,
            latitude=site.coordinates.lat if site.coordinates else None,
            longitude=site.coordinates.lng if site.coordinates else None,
        )

    @staticmethod
    def _event(
        event: AlarmEventResponse, definitions: dict[int, AlarmDefinitionResponse]
    ) -> AlarmEvent:
        definition = definitions.get(event.definition_id)
        return AlarmEvent(
            alarm_name=definition.name if definition else f"alarm {event.definition_id}",
            severity=AlarmSeverity(event.severity),
            message=event.message,
            device_id=event.device_id,
            raised_at=aware(event.raised_at),
            cleared_at=aware(event.cleared_at) if event.cleared_at else None,
        )
