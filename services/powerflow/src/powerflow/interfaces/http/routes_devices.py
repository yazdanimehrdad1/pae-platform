"""The site as PAE point-standard devices: /devices (the same devices, points and values the
Modbus server serves, as engineering values with enum and bit labels)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from powerflow.core.snapshot import Snapshot
from powerflow.errors import NoMeasurementError, UnknownAssetError, UnknownPointError
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses
from powerflow.point_standard import Device, DeviceKind, build_layout
from powerflow.point_standard.readings import (
    DeviceInfo,
    DevicesSnapshot,
    read_device,
    read_devices,
    resolve_point,
)
from powerflow.point_standard.sources import sources_from

router = APIRouter(prefix="/devices", tags=["devices"])
ERRORS: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "No such device or point."},
    409: {"model": ErrorResponse, "description": "No step has run yet."},
}
MAX_HISTORY_POINTS = 20


class HistoryPoint(BaseModel):
    point: str
    label: str
    unit: str


class DeviceSample(BaseModel):
    step_id: int
    sim_time: datetime
    converged: bool
    values: list[float | None] = Field(description="One per requested point, in order.")


class DeviceHistory(DeviceInfo):
    points: list[HistoryPoint]
    samples: list[DeviceSample]


def _latest(context: AdapterContext) -> Snapshot:
    latest = context.engine.store.latest
    if latest is None:
        raise NoMeasurementError("no step has run yet: POST /api/sim/start")
    return latest


def _devices(context: AdapterContext) -> tuple[Device, ...]:
    return build_layout(context.engine.config, context.point_standard)


def _device(context: AdapterContext, kind: DeviceKind, asset_id: str) -> Device:
    for device in _devices(context):
        if device.kind is kind and device.asset_id == asset_id:
            return device
    raise UnknownAssetError(f"no {kind} device {asset_id!r}")


@router.get(
    "",
    response_model=DevicesSnapshot,
    responses=ERRORS,
    summary="Every device's standard points, from the latest snapshot",
    description="The active site laid out by the PAE point standard (the Modbus server's "
    "devices), each point with its engineering value in SI units, standard enum/bit codes and "
    "their labels. `served: no` points are null (Modbus reads 0 there).",
)
async def list_devices(context: AdapterContext = Depends(get_context)) -> DevicesSnapshot:
    snapshot = _latest(context)
    engine = context.engine
    sources = sources_from(snapshot, engine.config, context.points, context.point_standard.enums)
    return read_devices(_devices(context), sources)


@router.get(
    "/{kind}/{asset_id}",
    response_model=DevicesSnapshot,
    responses=ERRORS,
    summary="One device's standard points, from the latest snapshot",
)
async def get_device(
    kind: DeviceKind, asset_id: str, context: AdapterContext = Depends(get_context)
) -> DevicesSnapshot:
    device = _device(context, kind, asset_id)
    snapshot = _latest(context)
    engine = context.engine
    sources = sources_from(snapshot, engine.config, context.points, context.point_standard.enums)
    return DevicesSnapshot(
        step_id=snapshot.step_id,
        sim_time=snapshot.sim_time,
        converged=snapshot.converged,
        devices=[read_device(device, sources)],
    )


@router.get(
    "/{kind}/{asset_id}/history",
    response_model=DeviceHistory,
    responses=ERRORS,
    summary="Standard points of one device over the in-memory history",
    description="Resolved from each historic snapshot (oldest first). Points derived from a "
    "setpoint are null: setpoints aren't recorded in history.",
)
async def device_history(
    kind: DeviceKind,
    asset_id: str,
    points: list[str] = Query(min_length=1, max_length=MAX_HISTORY_POINTS),
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    context: AdapterContext = Depends(get_context),
) -> DeviceHistory:
    device = _device(context, kind, asset_id)
    rows = {register.row.point: register.row for register in device.registers}
    unknown = [point for point in points if point not in rows]
    if unknown:
        raise UnknownPointError(f"{device.label} has no point(s) {unknown}")
    engine = context.engine
    enums = context.point_standard.enums
    samples: list[DeviceSample] = []
    for snapshot in engine.store.history(start, end):
        sources = sources_from(snapshot, engine.config, context.points, enums, historic=True)
        samples.append(
            DeviceSample(
                step_id=snapshot.step_id,
                sim_time=snapshot.sim_time,
                converged=snapshot.converged,
                values=[resolve_point(device, rows[point], sources) for point in points],
            )
        )
    return DeviceHistory(
        kind=device.kind,
        asset_id=device.asset_id,
        base=device.base,
        points=[
            HistoryPoint(point=point, label=rows[point].label, unit=rows[point].unit)
            for point in points
        ],
        samples=samples,
    )
