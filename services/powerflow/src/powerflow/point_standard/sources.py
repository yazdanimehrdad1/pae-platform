"""What a point resolver can see: one snapshot (with its energy counters), the site config, any
powerflow point by name, and the enum table. A resolver is `fn(sources, device) -> value | None`
(None leaves the register at 0)."""

from collections.abc import Callable
from dataclasses import dataclass

from powerflow.core.point_registry import PointRegistry
from powerflow.core.snapshot import Snapshot
from powerflow.point_standard.catalog import EnumTable
from powerflow.point_standard.layout import Device, DeviceKind
from powerflow.points import PointSource
from powerflow.site_config import SiteConfig

PointValue = float | int | bool


@dataclass(frozen=True)
class Sources:
    snapshot: Snapshot
    config: SiteConfig
    # A powerflow point by full name (`bess.bess1.p_setpoint_kw`). Measurement points come from
    # `snapshot`, setpoint and nameplate points from the engine.
    read: Callable[[str], PointValue]
    enums: EnumTable


Resolver = Callable[[Sources, Device], float | None]


def powerflow_prefix(device: Device) -> str:
    """The powerflow asset a device's points come from (`bess.bess1`, `poi.meter`, ...)."""
    match device.kind:
        case DeviceKind.BESS | DeviceKind.PV | DeviceKind.LOAD:
            return f"{device.kind}.{device.asset_id}"
        case DeviceKind.FEEDER_METER:
            return f"meter.{device.asset_id}"
        case DeviceKind.SITE | DeviceKind.POI_METER | DeviceKind.MET_STATION:
            return "poi.meter"


class SetpointNotRecorded(Exception):
    """A historic snapshot was asked for a setpoint: setpoints aren't kept in history."""


def sources_from(
    snapshot: Snapshot,
    config: SiteConfig,
    points: PointRegistry,
    enums: EnumTable,
    historic: bool = False,
) -> Sources:
    """Sources for one snapshot: measurement points from the snapshot, nameplate points from the
    engine (they can't change without a reset, which clears the history), setpoint points from
    the engine for the latest snapshot. For a historic one (`historic`), reading a setpoint raises
    SetpointNotRecorded, so a value that would mix today's setpoint into the past isn't made up."""

    def read(name: str) -> PointValue:
        _, definition = points.resolve(name)
        if definition.source is PointSource.MEASUREMENT:
            return points.read_from_snapshot(snapshot, name)
        if historic and definition.source is PointSource.SETPOINT:
            raise SetpointNotRecorded(name)
        return points.read(name)

    return Sources(snapshot=snapshot, config=config, read=read, enums=enums)
