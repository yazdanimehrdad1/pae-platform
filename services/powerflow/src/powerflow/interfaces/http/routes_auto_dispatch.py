"""Auto dispatch (/sim/auto-dispatch): each BESS cycles inside an SOC window on its own, so the
site runs without an EMS writing setpoints. Site-wide defaults, per-BESS overrides."""

from fastapi import APIRouter, Depends

from powerflow.core.auto_dispatch import AutoDispatchReport, AutoDispatchRequest
from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.interfaces.http.schemas import ErrorResponse, OpenApiResponses

router = APIRouter(prefix="/sim", tags=["auto dispatch"])
ERRORS: OpenApiResponses = {
    404: {"model": ErrorResponse, "description": "An override names no BESS of the active site."},
    422: {
        "model": ErrorResponse,
        "description": "Invalid settings, e.g. an SOC window outside a battery's band.",
    },
}


@router.get(
    "/auto-dispatch",
    response_model=AutoDispatchReport,
    summary="Auto dispatch now: on or off, its settings and each BESS's phase",
)
async def get_auto_dispatch(context: AdapterContext = Depends(get_context)) -> AutoDispatchReport:
    return context.engine.auto_dispatch_status()


@router.put(
    "/auto-dispatch",
    response_model=AutoDispatchReport,
    responses=ERRORS,
    summary="Turn auto dispatch on or off, or change its settings",
    description="On: each included BESS discharges at power_pct % of its rating down to its "
    "window's low edge, rests (rest_s), charges up to the high edge, rests, and repeats, with "
    "optional power noise, an extra ramp limit, a start direction and a fixed Q. `defaults` "
    "apply to every BESS and `bess` overrides them per BESS id (a field left out falls back). "
    "Setpoint writes to a driven BESS are 409 meanwhile (an alarm reset still goes); an excluded "
    "one takes them. Off, or excluded: the BESS goes back to idle. Works in any run state; a reset "
    "turns it off.",
)
async def put_auto_dispatch(
    request: AutoDispatchRequest, context: AdapterContext = Depends(get_context)
) -> AutoDispatchReport:
    return context.engine.set_auto_dispatch(request)
