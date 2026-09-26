"""Models for the alpha_solar site (src/site_profiles/individual_sites/alpha_solar/)."""

from datetime import datetime

from pydantic import BaseModel, Field

from schemas.api_models import PointTimeseries

# --- alpha_solar: poi-power ------------------------------------------------------------


class PoiPowerResult(BaseModel):
    site_id: int
    start_time: datetime
    end_time: datetime
    peak_kw: float | None = Field(None, description="Highest POI active power in the window; null if no readings")
    average_kw: float | None = Field(None, description="Mean of the samples in the window; null if no readings")
    series: PointTimeseries = Field(..., description="POI active power samples, oldest first")


# --- alpha_solar: inverter-availability ------------------------------------------------


class InverterAvailabilityResult(BaseModel):
    site_id: int
    device_id: int
    device_name: str
    start_time: datetime
    end_time: datetime
    state_points: list[str] = Field(..., description="The state points that were evaluated")
    online_states: list[int] = Field(..., description="State codes counted as available")
    sample_count: int
    online_sample_count: int
    availability_pct: float | None = Field(None, description="online / total samples x 100; null if no readings")
