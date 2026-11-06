"""Models for the Powerflow 2BESS 1PV site (src/site_profiles/individual_sites/powerflow_2bess_1pv/)."""

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.api_models import PointTimeseries
from schemas.site_profiles import RoundTripEfficiencyResult, RoundTripStatus, TimeWindowParams


class PowerSeriesResult(BaseModel):
    """A power series summed from SPF points; export positive, import negative."""

    site_id: int
    start_time: datetime
    end_time: datetime
    unit: str = Field(..., description="kW or kvar")
    peak: float | None = Field(None, description="Highest value in the window; null if no values")
    average: float | None = Field(
        None, description="Mean of the values in the window; null if no values"
    )
    series: PointTimeseries = Field(
        ..., description="The value at each poll timestamp, oldest first (id 0: computed)"
    )


class BessRoundTripEfficiencyResult(BaseModel):
    """One BESS's round trip efficiency over the requested window."""

    site_id: int
    start_time: datetime
    end_time: datetime
    bess: str = Field(..., description="The BESS device's name")
    round_trip: RoundTripEfficiencyResult


class RollingRoundTripEfficiencyParams(TimeWindowParams):
    """The window to chart, plus how far back each value looks."""

    lookback_days: int = Field(
        7,
        ge=1,
        le=90,
        description="Each value is the round trip efficiency over the last N days",
    )


class BessRollingRoundTripEfficiencyResult(BaseModel):
    """One BESS's round trip efficiency at every whole step in the window, each over the last
    lookback_days. The step follows the window: 1 min up to 1 hour, 15 min under a week, else 1 hour.
    """

    site_id: int
    start_time: datetime
    end_time: datetime
    bess: str = Field(..., description="The BESS device's name")
    lookback_days: int
    step_minutes: int = Field(
        ..., description="Minutes between values: 1, 15 or 60, from the window's length"
    )
    values_by_status: dict[RoundTripStatus, int] = Field(
        ...,
        description="How many values had each status; only ok and above_100_percent have a value",
    )
    series: PointTimeseries = Field(
        ...,
        description="Round trip efficiency (%) at each whole step, oldest first; null where not computed",
    )


class LatestPointValue(BaseModel):
    """A point's latest fresh reading, as the site's alarm checks use it."""

    value: float
    bits: frozenset[str] = Field(
        frozenset(), description="A bitfield point's set bits, by label; empty for other points"
    )
