"""Models for the Powerflow 2BESS 1PV site (src/site_profiles/individual_sites/powerflow_2bess_1pv/)."""

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.api_models import PointTimeseries


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
