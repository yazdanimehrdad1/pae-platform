"""Measurements: /measurements/latest, /measurements/poi, /measurements/history."""

import csv
import io
from datetime import datetime
from enum import StrEnum

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from powerflow.core.snapshot import Snapshot
from powerflow.errors import NoMeasurementError
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import (
    ErrorResponse,
    HistoryResponse,
    HistoryValue,
    OpenApiResponses,
    PoiResponse,
)
from powerflow.points import PointSource

router = APIRouter(prefix="/measurements", tags=["measurements"])
NO_DATA: OpenApiResponses = {409: {"model": ErrorResponse, "description": "No step has run yet."}}


class HistoryFormat(StrEnum):
    JSON = "json"
    CSV = "csv"


def _latest(context: AdapterContext) -> Snapshot:
    latest = context.engine.store.latest
    if latest is None:
        raise NoMeasurementError("no step has run yet: POST /api/sim/start")
    return latest


@router.get(
    "/latest",
    response_model=Snapshot,
    responses=NO_DATA,
    summary="The full latest snapshot",
    description="POI, every bus, every transformer, every asset (commanded vs actual), losses "
    "and the convergence flag. `step_id` increases by one per sim tick, so a poller can spot "
    "missed steps and backfill from /measurements/history.",
)
async def latest(context: AdapterContext = Depends(get_context)) -> Snapshot:
    return _latest(context)


@router.get("/poi", response_model=PoiResponse, responses=NO_DATA, summary="The POI meter")
async def poi(context: AdapterContext = Depends(get_context)) -> PoiResponse:
    snapshot = _latest(context)
    return PoiResponse(
        step_id=snapshot.step_id,
        sim_time=snapshot.sim_time,
        converged=snapshot.converged,
        poi=snapshot.poi,
    )


@router.get(
    "/history",
    response_model=HistoryResponse,
    responses={
        200: {"content": {"text/csv": {"schema": {"type": "string"}}}},
        404: {"model": ErrorResponse, "description": "Unknown field."},
        422: {"model": ErrorResponse, "description": "Field is not a measurement point."},
    },
    summary="Snapshots from the in-memory ring buffer, as rows of point values",
)
async def history(
    start: datetime | None = Query(default=None, alias="from", description="Sim time ≥ from."),
    end: datetime | None = Query(default=None, alias="to", description="Sim time ≤ to."),
    fields: str | None = Query(
        default=None,
        description="Comma-separated measurement point names (e.g. "
        "`poi.meter.p_kw,bess.bess1.soc_pct`). Default: every measurement point.",
    ),
    output_format: HistoryFormat = Query(default=HistoryFormat.JSON, alias="format"),
    context: AdapterContext = Depends(get_context),
) -> HistoryResponse | Response:
    registry = context.points
    if fields:
        names = [name.strip() for name in fields.split(",") if name.strip()]
    else:
        names = registry.names(PointSource.MEASUREMENT)
    snapshots = context.engine.store.history(start, end)
    rows: list[dict[str, HistoryValue]] = []
    for snapshot in snapshots:
        row: dict[str, HistoryValue] = {
            "sim_time": snapshot.sim_time.isoformat(),
            "step_id": snapshot.step_id,
        }
        for name in names:
            row[name] = registry.read_from_snapshot(snapshot, name)
        rows.append(row)

    if output_format is HistoryFormat.CSV:
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=["sim_time", "step_id", *names], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
        return Response(content=buffer.getvalue(), media_type="text/csv")
    return HistoryResponse(count=len(rows), fields=names, rows=rows)
