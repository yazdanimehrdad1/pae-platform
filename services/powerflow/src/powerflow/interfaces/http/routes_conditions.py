"""Injected conditions: /sim/conditions (breakers, asset faults, alarm resets, comm loss, grid
events), the fault cause catalog (/sim/fault-causes) and the event scenario player
(/sim/event-scenario)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from powerflow.conditions import ConditionChange, FaultCauseInfo, catalog_info
from powerflow.conditions.scenario import ConditionsReport
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses

router = APIRouter(prefix="/sim", tags=["conditions"])
ERRORS: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "No such asset, meter, breaker or scenario."},
    409: {
        "model": ErrorResponse,
        "description": "That event scenario is already scheduled or playing.",
    },
    422: {"model": ErrorResponse, "description": "The change doesn't apply to this site."},
}


class StartScenarioRequest(BaseModel):
    name: str
    at_step: int | None = Field(
        default=None,
        ge=1,
        description="The engine step that is the scenario's step 1 (after the current step); "
        "null = the next step.",
    )


class StopScenarioRequest(BaseModel):
    name: str | None = Field(default=None, description="The run to stop; null = every run.")


@router.get(
    "/fault-causes",
    response_model=list[FaultCauseInfo],
    summary="The fault causes per asset type and the points they drive",
    description="Faults trip the inverter and latch when cleared (until an alarm reset) unless "
    "injected with auto_restore; warnings derate it and clear at once.",
)
async def get_fault_causes() -> list[FaultCauseInfo]:
    return catalog_info()


@router.get("/conditions", response_model=ConditionsReport, summary="The injected conditions now")
async def get_conditions(context: AdapterContext = Depends(get_context)) -> ConditionsReport:
    return context.engine.active_conditions()


@router.post(
    "/conditions",
    response_model=ConditionsReport,
    responses=ERRORS,
    summary="Apply one condition change now",
    description="Open/close a breaker, fault or clear an asset (a cleared fault latches until an "
    "alarm_reset, unless it was injected with auto_restore), reset an asset's alarms, lose or "
    "restore comms, or set the grid voltage/frequency. Works in any run state; the next step "
    "applies it.",
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
    "with no faults (latched ones included), comm loss or grid events.",
)
async def clear_conditions(context: AdapterContext = Depends(get_context)) -> ConditionsReport:
    return context.engine.clear_conditions()


@router.post(
    "/event-scenario/start",
    response_model=ConditionsReport,
    responses=ERRORS,
    summary="Play or schedule a stored event scenario of the active site",
    description="Its step 1 is the next engine step, or `at_step`. Several scenarios can be "
    "scheduled or playing at once; where they change the same thing, the later change wins.",
)
async def start_scenario(
    request: StartScenarioRequest, context: AdapterContext = Depends(get_context)
) -> ConditionsReport:
    return await context.scenarios.start(request.name, request.at_step)


@router.post(
    "/event-scenario/stop",
    response_model=ConditionsReport,
    responses=ERRORS,
    summary="Stop one event scenario run, or all (their conditions stay)",
)
async def stop_scenario(
    request: StopScenarioRequest | None = None, context: AdapterContext = Depends(get_context)
) -> ConditionsReport:
    return await context.engine.stop_scenario(request.name if request is not None else None)
