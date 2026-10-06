"""Where every point of every device sits in the aggregator's register space.

One Modbus server, one unit id; each device owns a 100-register chunk:

| Group            | Base | Devices                                               |
|------------------|------|-------------------------------------------------------|
| Site             | 0    | plant controller at 0, met station at 100 (if any PV  |
|                  |      | is irradiance-driven); the site group ends at 499     |
| BESS             | 1000 | BESS n at 1000 + 100·(n−1)                            |
| PV               | 2000 | PV n at 2000 + 100·(n−1)                              |
| Gensets / loads  | 3000 | load n at 3000 + 100·(n−1) (powerflow has no gensets) |
| Meters / relays  | 4000 | POI meter at 4000, feeder meters from 4100            |

Within a chunk, points are packed in CSV order, followed by common.csv's rows. Every row gets an
address, served or not, so serving more points later never moves an existing one.
"""

from dataclasses import dataclass
from enum import StrEnum

from powerflow.errors import PointStandardError
from powerflow.point_standard.catalog import COMMON_FILE, PointRow, PointStandard
from powerflow.site_config import PvAvailabilitySource, SiteConfig

CHUNK_REGISTERS = 100
REGISTER_SPACE = 5000  # 0..4999: the five groups of 1000


class DeviceKind(StrEnum):
    SITE = "site"
    MET_STATION = "met_station"
    BESS = "bess"
    PV = "pv"
    LOAD = "load"
    POI_METER = "poi_meter"
    FEEDER_METER = "feeder_meter"


POINT_LIST_FILE: dict[DeviceKind, str] = {
    DeviceKind.SITE: "plant_controller.csv",
    DeviceKind.MET_STATION: "met_station.csv",
    DeviceKind.BESS: "bess.csv",
    DeviceKind.PV: "pv_inverter.csv",
    DeviceKind.LOAD: "load.csv",
    DeviceKind.POI_METER: "meter.csv",
    DeviceKind.FEEDER_METER: "meter.csv",
}
GROUP_BASE = {"site": 0, "bess": 1000, "pv": 2000, "gen_load": 3000, "meter": 4000}
GROUP_SIZE = 1000
# Device ids in the Modbus layout (not powerflow asset ids: those are in powerflow.points).
SITE_DEVICE_ID = "site"
MET_STATION_DEVICE_ID = "met"
POI_METER_DEVICE_ID = "meter"


@dataclass(frozen=True)
class Register:
    address: int
    row: PointRow


@dataclass(frozen=True)
class Device:
    kind: DeviceKind
    asset_id: str
    base: int
    registers: tuple[Register, ...]

    @property
    def label(self) -> str:
        return f"{self.kind}.{self.asset_id}"


def device_template(standard: PointStandard, kind: DeviceKind) -> tuple[Register, ...]:
    """A device kind's registers with addresses as offsets from the device base: its point list
    in CSV order, then common.csv's. Fails if they don't fit a 100-register chunk."""
    registers: list[Register] = []
    offset = 0
    for row in (*standard.rows(POINT_LIST_FILE[kind]), *standard.rows(COMMON_FILE)):
        registers.append(Register(offset, row))
        offset += row.width
    if offset > CHUNK_REGISTERS:
        raise PointStandardError(
            f"{kind}: {offset} registers don't fit its {CHUNK_REGISTERS}-register chunk"
        )
    return tuple(registers)


def _device(standard: PointStandard, kind: DeviceKind, asset_id: str, base: int) -> Device:
    registers = tuple(
        Register(base + item.address, item.row) for item in device_template(standard, kind)
    )
    return Device(kind, asset_id, base, registers)


def _group(
    standard: PointStandard,
    kind: DeviceKind,
    asset_ids: list[str],
    group_base: int,
    first_slot: int = 0,
) -> list[Device]:
    """Consecutive chunks from `group_base + first_slot·100`, within the group's 1000."""
    if (first_slot + len(asset_ids)) * CHUNK_REGISTERS > GROUP_SIZE:
        raise PointStandardError(
            f"{len(asset_ids)} {kind} devices don't fit the {GROUP_SIZE}-register group at "
            f"{group_base}"
        )
    return [
        _device(standard, kind, asset_id, group_base + (first_slot + index) * CHUNK_REGISTERS)
        for index, asset_id in enumerate(asset_ids)
    ]


def build_layout(config: SiteConfig, standard: PointStandard) -> tuple[Device, ...]:
    """Every device of the site, at its base address."""
    devices = _group(standard, DeviceKind.SITE, [SITE_DEVICE_ID], GROUP_BASE["site"])
    if any(pv.availability.source is PvAvailabilitySource.IRRADIANCE for pv in config.pv):
        devices += _group(
            standard, DeviceKind.MET_STATION, [MET_STATION_DEVICE_ID], 0, first_slot=1
        )
    devices += _group(
        standard, DeviceKind.BESS, [bess.id for bess in config.bess], GROUP_BASE["bess"]
    )
    devices += _group(standard, DeviceKind.PV, [pv.id for pv in config.pv], GROUP_BASE["pv"])
    devices += _group(
        standard, DeviceKind.LOAD, [load.id for load in config.loads], GROUP_BASE["gen_load"]
    )
    devices += _group(standard, DeviceKind.POI_METER, [POI_METER_DEVICE_ID], GROUP_BASE["meter"])
    devices += _group(
        standard,
        DeviceKind.FEEDER_METER,
        [meter.id for meter in config.meters],
        GROUP_BASE["meter"],
        first_slot=1,
    )
    return tuple(devices)
