"""Shared builders for the reports unit tests: a site with two devices and its functions."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from reports.blocks import BlockContext
from schemas.api_models import DevicePointResponse
from schemas.reports.api import ReportSiteFunction
from schemas.reports.internal import ReportSiteContext
from unit.reports.fake_data_source import FakeReportDataSource
from unit.site_fixtures import make_device, make_point, make_site

WINDOW_START = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 14, 7, 0, tzinfo=UTC)

POWER = make_point(11, 1, "active_power").model_copy(update={"unit": "kW"})
SOC = make_point(12, 1, "soc").model_copy(update={"unit": "%"})
INVERTER_STATE = make_point(21, 2, "inverter_state")

FUNCTIONS = [
    ReportSiteFunction(
        name="site-energy-summary", kind="site", output="scalar", summary="energy", numeric_fields=["energy_kwh"]
    ),
    ReportSiteFunction(
        name="site-poi-power", kind="site", output="series", summary="poi", numeric_fields=["peak_kw", "average_kw"]
    ),
    ReportSiteFunction(
        name="device-inverter-availability", kind="device", output="scalar", summary="availability",
        device_types=["INVERTER"], numeric_fields=["availability_pct"],
    ),
]


def site_context(points: list[DevicePointResponse] | None = None) -> ReportSiteContext:
    bess = make_device(1, [POWER, SOC], device_type="BESS")
    inverter = make_device(2, [INVERTER_STATE], device_type="INVERTER")
    if points is not None:
        bess = make_device(1, points, device_type="BESS")
    return ReportSiteContext(site=make_site(), devices=[bess, inverter], functions=FUNCTIONS)


def block_context(data_source: FakeReportDataSource, timezone: str = "America/Los_Angeles") -> BlockContext:
    return BlockContext(
        site=site_context(),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        site_timezone=ZoneInfo(timezone),
        data_source=data_source,
    )
