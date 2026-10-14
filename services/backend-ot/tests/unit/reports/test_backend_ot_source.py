"""
Unit tests for the pure part of reports.backend_ot_source.

Guards which fields of a site function's result the report builder offers as KPIs: top-level int
and float fields, optional ones included, never ids, booleans, strings, lists or nested models.
"""

from datetime import datetime

from pydantic import BaseModel

from reports.backend_ot_source import numeric_fields
from schemas.site_profiles import EnergySummaryResult
from schemas.site_profiles.individual_sites.alpha_solar import (
    InverterAvailabilityResult,
    PoiPowerResult,
)


class Mixed(BaseModel):
    id: int
    site_id: int
    count: int
    ratio: float | None
    ok: bool
    label: str
    when: datetime
    values: list[float]


class TestNumericFields:
    def test_keeps_numbers_drops_ids_and_everything_else(self):
        assert numeric_fields(Mixed) == ["count", "ratio"]

    def test_alpha_solar_results(self):
        assert numeric_fields(EnergySummaryResult) == ["energy_kwh"]
        assert numeric_fields(PoiPowerResult) == ["peak_kw", "average_kw"]
        assert numeric_fields(InverterAvailabilityResult) == ["sample_count", "online_sample_count", "availability_pct"]
