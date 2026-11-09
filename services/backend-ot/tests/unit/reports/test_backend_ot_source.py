"""
Unit tests for the pure part of reports.backend_ot_source.

Guards which fields of a site function's result the report builder offers as KPIs: top-level int
and float fields, optional ones included, never ids, booleans, strings, lists or nested models.
"""

from datetime import datetime

from pydantic import BaseModel

from reports.backend_ot_source import numeric_fields, report_functions
from schemas.site_profiles import EnergySummaryResult
from schemas.site_profiles.individual_sites.alpha_solar import (
    InverterAvailabilityResult,
    PoiPowerResult,
)
from site_profiles.declarations.endpoint import SiteEndpoint
from site_profiles.individual_sites.alpha_solar.alpha_solar_functions import site_energy_summary


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


class TestReportFunctions:
    def test_ai_only_functions_are_not_offered_to_reports(self):
        endpoints = [endpoint_for("site-energy-summary", user_visible=True), endpoint_for("site-ai-only", user_visible=False)]
        assert [function.name for function in report_functions(endpoints)] == ["site-energy-summary"]

    def test_ai_labelled_function_that_users_see_is_offered(self):
        endpoints = [endpoint_for("site-energy-summary", user_visible=True, ai_assistant=True)]
        assert [function.name for function in report_functions(endpoints)] == ["site-energy-summary"]


def endpoint_for(name: str, *, user_visible: bool, ai_assistant: bool = True) -> SiteEndpoint:
    return SiteEndpoint(
        method="GET",
        kind="site",
        name=name,
        controller=site_energy_summary,
        response_model=EnergySummaryResult,
        summary="energy",
        user_visible=user_visible,
        ai_assistant=ai_assistant,
    )
