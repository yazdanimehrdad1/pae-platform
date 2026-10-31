"""
The standard shape of a point a site profile's functions read (an SPF point).

A site declares its SPF points once, in individual_sites/<site>/<site>_points.py, and its
functions use only those:

    SPF_BESS1_ACTIVE_POWER = SpfPoint(
        device="2bess_1pv-bess1",          # the device's name
        point="BESS_ACTIVE_POWER",         # the point's name on it (STANDARDIZED where one exists)
        category="STANDARDIZED",           # where the point comes from: NATIVE, STANDARDIZED or VIRTUAL
        scale=1.0,                         # multiplier to the function's unit (W -> kW: 0.001)
        sign=1,                            # +1 or -1, so the value reads export positive
    )

A point is referenced by name, never by id: names are the same in every environment, ids aren't.
`category` records the point's origin for whoever reads or debugs the declaration; nothing reads
it yet.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["SpfPoint"]


class SpfPoint(BaseModel):
    """One device point a site function reads, with the scale and sign to apply to its value."""

    model_config = ConfigDict(frozen=True)

    device: str = Field(
        ..., min_length=1, description="The name of the site's device the point is on"
    )
    point: str = Field(..., min_length=1, description="The point's name on that device")
    category: Literal["NATIVE", "STANDARDIZED", "VIRTUAL"] = Field(
        ..., description="The point's origin on the device (informational; not used to find it)"
    )
    scale: float = Field(
        ..., description="Multiplier to the function's unit, e.g. 0.001 for W -> kW"
    )
    sign: float = Field(
        ..., description="+1 or -1, so the value reads export positive, import negative"
    )
