"""Injected conditions: /sim/conditions (breakers, asset faults, comm loss, grid events) and the
event scenario player (/sim/event-scenario)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from powerflow.conditions import ConditionChange
from powerflow.conditions.scenario import ConditionsReport
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses

router = APIRouter(prefix="/sim", tags=["conditions"])
ERRORS: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "No such asset, meter, breaker or scenario."},
    409: {"model": ErrorResponse, "description": "Another event scenario is playing."},
    422: {"model": ErrorResponse, "description": "The change doesn't apply to this site."},
}


class StartScenarioRequest(BaseModel):
    name: str


@router.get("/conditions", response_model=ConditionsReport, summary="The injected conditions now")
async def get_conditions(context: AdapterContext = Depends(get_context)) -> ConditionsReport:
    return context.engine.active_conditions()


@router.post(
    "/conditions",
    response_model=ConditionsReport,
    responses=ERRORS,
    summary="Apply one condition change now",
    description="Open/close a breaker, fault or clear an asset, lose or restore comms, or set "
    "the grid voltage/frequency. Works in any run state; the next step applies it.",
)
async def apply_condition(
    change: ConditionChange, context: AdapterContext = Depends(get_context)
) -> ConditionsReport:
    return context.engine.apply_condition(change)


@router.post(
    "/conditions/clear",
    response_model=ConditionsReport,
    summary="Clear every injected condition",
    description="Stops the event scenario and returns to the site config's breaker positions, "
    "with no faults, comm loss or grid events.",
)
async def clear_conditions(context: AdapterContext = Depends(get_context)) -> ConditionsReport:
    return context.engine.clear_conditions()


@router.post(
    "/event-scenario/start",
    response_model=ConditionsReport,
    responses=ERRORS,
    summary="Play a stored event scenario of the active site",
    description="Its events fire from the current step on (step triggers count from here).",
)
async def start_scenario(
    request: StartScenarioRequest, context: AdapterContext = Depends(get_context)
) -> ConditionsReport:
    return await context.scenarios.start(request.name)


@router.post(
    "/event-scenario/stop",
    response_model=ConditionsReport,
    summary="Stop the event scenario (its conditions stay)",
)
async def stop_scenario(context: AdapterContext = Depends(get_context)) -> ConditionsReport:
    return await context.engine.stop_scenario()
