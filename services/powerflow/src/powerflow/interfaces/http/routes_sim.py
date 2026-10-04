"""Simulation control: /sim/*."""

from fastapi import APIRouter, Body, Depends, Query
from pydantic import AwareDatetime, BaseModel, Field

from powerflow.core.engine import MAX_MANUAL_STEPS, EngineStatus
from powerflow.core.snapshot import Snapshot
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses

router = APIRouter(prefix="/sim", tags=["simulation"])
CONFLICT: OpenApiResponses = {
    409: {"model": ErrorResponse, "description": "Not allowed in the current state."}
}


@router.get("/status", response_model=EngineStatus, summary="Engine state and counters")
async def status(context: AdapterContext = Depends(get_context)) -> EngineStatus:
    return context.engine.status()


class StartRequest(BaseModel):
    at: AwareDatetime | None = Field(
        default=None,
        description="Start at this wall-clock time (state SCHEDULED until then); omitted or "
        "past = now.",
    )


class SpeedRequest(BaseModel):
    speed: float = Field(gt=0, le=100, description="Sim seconds per wall-clock second.")


@router.post(
    "/start",
    response_model=EngineStatus,
    summary="Start or resume real-time (now, or scheduled)",
    description="No body (or no `at`) starts now. A start replaces a pending schedule; "
    "POST /sim/stop cancels one.",
)
async def start(
    request: StartRequest | None = Body(default=None),
    context: AdapterContext = Depends(get_context),
) -> EngineStatus:
    await context.engine.start(request.at if request is not None else None)
    return context.engine.status()


@router.put(
    "/speed",
    response_model=EngineStatus,
    summary="Set the speed factor",
    description="Sim seconds per wall-clock second (0 < speed ≤ 100), until reset or the site "
    "is reloaded (then simulation.speed applies). A running loop re-anchors.",
)
async def set_speed(
    request: SpeedRequest, context: AdapterContext = Depends(get_context)
) -> EngineStatus:
    await context.engine.set_speed(request.speed)
    return context.engine.status()


@router.post("/pause", response_model=EngineStatus, responses=CONFLICT, summary="Pause")
async def pause(context: AdapterContext = Depends(get_context)) -> EngineStatus:
    await context.engine.pause()
    return context.engine.status()


@router.post("/stop", response_model=EngineStatus, summary="Stop (state kept)")
async def stop(context: AdapterContext = Depends(get_context)) -> EngineStatus:
    await context.engine.stop()
    return context.engine.status()


@router.post("/reset", response_model=EngineStatus, summary="Stop and return to the initial state")
async def reset(context: AdapterContext = Depends(get_context)) -> EngineStatus:
    await context.engine.reset()
    return context.engine.status()


@router.post(
    "/step",
    response_model=Snapshot,
    responses=CONFLICT,
    summary="Advance N steps at once (test mode only)",
    description="Only with `simulation.test_mode: true` and while not running; otherwise 409. "
    "Returns the last step's snapshot.",
)
async def step(
    count: int = Query(default=1, ge=1, le=MAX_MANUAL_STEPS),
    context: AdapterContext = Depends(get_context),
) -> Snapshot:
    return await context.engine.step(count)
