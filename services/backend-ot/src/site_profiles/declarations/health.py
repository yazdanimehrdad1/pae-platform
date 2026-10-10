"""
The standard shape of a device health check a site profile declares in code.

A profile lists one check per SLD element type that shows health (bess, pv):

    DeviceHealthCheck(
        node_type="bess",
        evaluate=bess_health,        # async (DeviceHealthContext) -> DeviceHealth
    )

GET /api/sites/{site_id}/sld/values runs it for every SLD element of that type that is linked to
a device, and the element's info box shows the verdict. The check lives in site_profiles/common/
(shared) or in the profile's own package (site-specific), and may combine both.
"""

import inspect
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.site_profiles import DeviceHealth, DeviceHealthContext

__all__ = ["DeviceHealth", "DeviceHealthCheck", "DeviceHealthContext", "HealthEvaluator", "HealthNodeType"]

HealthNodeType = Literal["bess", "pv"]
"""The SLD element types whose info box shows health."""

HealthEvaluator = Callable[[DeviceHealthContext], Awaitable[DeviceHealth]]
"""The standard check signature: async def <name>(ctx: DeviceHealthContext) -> DeviceHealth."""


class DeviceHealthCheck(BaseModel):
    """How a site judges the health of the devices behind one SLD element type."""

    model_config = ConfigDict(frozen=True)

    node_type: HealthNodeType
    evaluate: HealthEvaluator = Field(..., description="The async check, run per linked element")

    @field_validator("evaluate")
    @classmethod
    def _evaluate_is_async(cls, evaluate: HealthEvaluator) -> HealthEvaluator:
        if not inspect.iscoroutinefunction(evaluate):
            raise ValueError(f"evaluate {evaluate!r} must be an 'async def' function")
        return evaluate
