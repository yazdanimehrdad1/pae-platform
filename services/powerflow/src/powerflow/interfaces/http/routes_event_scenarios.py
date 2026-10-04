"""Stored event scenarios, per site: /sites/{site}/event-scenarios."""

from fastapi import APIRouter, Depends, Response

from powerflow.conditions.scenario import EventScenario, EventScenarioSummary
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses

router = APIRouter(prefix="/sites/{site}/event-scenarios", tags=["event scenarios"])
ERRORS: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "No such site or event scenario."},
    422: {"model": ErrorResponse, "description": "Invalid name, or an event doesn't fit the site."},
}


@router.get(
    "",
    response_model=list[EventScenarioSummary],
    responses=ERRORS,
    summary="The site's event scenarios",
    description="Each is re-checked against the site as stored now (`valid`, `problems`).",
)
async def list_event_scenarios(
    site: str, context: AdapterContext = Depends(get_context)
) -> list[EventScenarioSummary]:
    return await context.scenarios.list(site)


@router.get("/{name}", response_model=EventScenario, responses=ERRORS, summary="One scenario")
async def get_event_scenario(
    site: str, name: str, context: AdapterContext = Depends(get_context)
) -> EventScenario:
    return await context.scenarios.get(site, name)


@router.put(
    "/{name}",
    response_model=EventScenario,
    responses=ERRORS,
    summary="Create or replace a scenario",
    description="Every event's change is validated against the site's stored config.",
)
async def put_event_scenario(
    site: str, name: str, scenario: EventScenario, context: AdapterContext = Depends(get_context)
) -> EventScenario:
    return await context.scenarios.save(site, name, scenario)


@router.delete("/{name}", status_code=204, responses=ERRORS, summary="Delete a scenario")
async def delete_event_scenario(
    site: str, name: str, context: AdapterContext = Depends(get_context)
) -> Response:
    await context.scenarios.delete(site, name)
    return Response(status_code=204)
