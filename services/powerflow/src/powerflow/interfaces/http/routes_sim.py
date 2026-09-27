"""Simulation control: /sim/*."""

from fastapi import APIRouter, Depends, Query

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


@router.post("/start", response_model=EngineStatus, summary="Start or resume real-time")
async def start(context: AdapterContext = Depends(get_context)) -> EngineStatus:
    await context.engine.start()
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
