"""The PAE point standard as readings: each device's points with their engineering values (SI
units, standard enum/bit codes), resolved by the same code that fills the Modbus registers. The
HTTP device view (/api/devices) serves these.

A reading's `value` is the resolver's value before register encoding: the Modbus register holds
round(value / scale), saturated to the data type. Points the simulator doesn't serve (`no`) and
values a resolver can't produce read null here (the register reads 0).
"""

import math
from datetime import datetime

from pydantic import BaseModel, Field

from powerflow.point_standard.catalog import PointRow, ServerSupport
from powerflow.point_standard.layout import Device, DeviceKind
from powerflow.point_standard.registers import resolver_for
from powerflow.point_standard.sources import SetpointNotRecorded, Sources


class PointReading(BaseModel):
    point: str = Field(description="Standard point name (SunSpec where one exists).")
    label: str
    unit: str = Field(description="SI unit, no prefix (W, var, V, A, Hz, Wh, %, ...).")
    data_type: str
    served: ServerSupport = Field(description="yes / calc: simulated; no: not served (null).")
    value: float | None = Field(description="Engineering value; null when not served.")
    text: str | None = Field(
        default=None, description="Enum: the code's label. Bitfield: the set bits' labels."
    )


class DeviceInfo(BaseModel):
    kind: DeviceKind
    asset_id: str = Field(description="The Modbus device id (site, met, meter, or the asset id).")
    base: int = Field(description="First Modbus register of the device's 100-register chunk.")


class DeviceReadings(DeviceInfo):
    points: list[PointReading]


class DevicesSnapshot(BaseModel):
    step_id: int
    sim_time: datetime
    converged: bool
    devices: list[DeviceReadings]


def _text(row: PointRow, value: float) -> str | None:
    if row.enum_detail is not None:
        return row.enum_detail.get(str(int(value)))
    if row.bitfield_detail is not None:
        bits = int(value)
        labels = [label for bit, label in row.bitfield_detail.items() if bits >> int(bit) & 1]
        return ", ".join(labels)
    return None


def resolve_point(device: Device, row: PointRow, sources: Sources) -> float | None:
    """The point's engineering value; None if unserved, unresolvable, or (historic sources) a
    value that needs a setpoint history doesn't keep."""
    resolver = resolver_for(device.kind, row)
    if resolver is None:
        return None
    try:
        value = resolver(sources, device)
    except SetpointNotRecorded:
        return None
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def read_device(device: Device, sources: Sources) -> DeviceReadings:
    points: list[PointReading] = []
    for register in device.registers:
        row = register.row
        value = resolve_point(device, row, sources)
        points.append(
            PointReading(
                point=row.point,
                label=row.label,
                unit=row.unit,
                data_type=row.data_type,
                served=row.support,
                value=value,
                text=_text(row, value) if value is not None else None,
            )
        )
    return DeviceReadings(
        kind=device.kind, asset_id=device.asset_id, base=device.base, points=points
    )


def read_devices(devices: tuple[Device, ...], sources: Sources) -> DevicesSnapshot:
    snapshot = sources.snapshot
    return DevicesSnapshot(
        step_id=snapshot.step_id,
        sim_time=snapshot.sim_time,
        converged=snapshot.converged,
        devices=[read_device(device, sources) for device in devices],
    )
