"""
Models shared by every site profile: the query window all site functions accept, the
per-request SiteContext, the discovery response, and the results of the common functions.
"""

from datetime import datetime
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from helpers.common.date_time import (
    TimeRange,
    normalize_to_utc,
    resolve_time_range,
    resolve_timezone,
)
from schemas.api_models import DevicePointResponse, DeviceWithPoints, SiteResponse

FunctionKind = Literal["common", "site", "device"]


# --- Query window ------------------------------------------------------------------------


class TimeWindow(BaseModel):
    """A resolved query window: aware UTC bounds plus the zone to render results in."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    start_time: datetime
    end_time: datetime
    display_tz: ZoneInfo | None = None

    def display(self, value: datetime) -> datetime:
        """Render an aware UTC datetime in the requested zone (same instant)."""
        return value if self.display_tz is None else value.astimezone(self.display_tz)


class TimeWindowParams(BaseModel):
    """
    Query parameters every site function accepts. A function that needs more parameters
    subclasses this and adds flat (query-string) fields.

    Pick one window: `time_range` (relative to now), or `start_time` with an optional
    `end_time` (defaults to now). Bounds follow the same timezone rules as the
    device-point-readings endpoints.
    """

    start_time: datetime | None = Field(
        None,
        description="Window start (ISO 8601 with a UTC offset, or naive with tz). Cannot be combined with time_range.",
    )
    end_time: datetime | None = Field(
        None,
        description="Window end; defaults to now. Needs start_time. Cannot be combined with time_range.",
    )
    time_range: TimeRange | None = Field(
        None, description="Relative window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M."
    )
    tz: str | None = Field(
        None,
        description="IANA timezone (or US shorthand such as 'PT') for naive bounds and for response timestamps.",
    )

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        if self.time_range is not None and (self.start_time or self.end_time):
            raise ValueError("Use either time_range or start_time/end_time, not both")
        if self.time_range is None and self.start_time is None:
            raise ValueError("Provide time_range, or start_time (with an optional end_time)")
        display_tz = resolve_timezone(self.tz) if self.tz else None
        if self.start_time is not None:
            start = normalize_to_utc(self.start_time, "start_time", display_tz)
            if self.end_time is not None:
                end = normalize_to_utc(self.end_time, "end_time", display_tz)
                if start >= end:
                    raise ValueError("start_time must be before end_time")
        return self

    def resolve_window(self) -> TimeWindow:
        """Resolve to aware UTC bounds. Reads the clock for time_range and a missing end_time."""
        display_tz = resolve_timezone(self.tz) if self.tz else None
        if self.time_range is not None:
            start, end = resolve_time_range(self.time_range)
            return TimeWindow(start_time=start, end_time=end, display_tz=display_tz)
        if self.start_time is None:  # unreachable: _check_window requires one of the two
            raise ValueError("Provide time_range, or start_time (with an optional end_time)")
        start = normalize_to_utc(self.start_time, "start_time", display_tz)
        end = (
            normalize_to_utc(self.end_time, "end_time", display_tz)
            if self.end_time is not None
            else datetime.now(start.tzinfo)
        )
        return TimeWindow(start_time=start, end_time=end, display_tz=display_tz)


# --- Per-request context -----------------------------------------------------------------


class SiteContext(BaseModel):
    """What a site function gets to work with: the site, its devices and their points."""

    site: SiteResponse
    devices: list[DeviceWithPoints]
    device: DeviceWithPoints | None = Field(None, description="The target device for device-level calls")

    def points_named(
        self, name: str, devices: list[DeviceWithPoints] | None = None
    ) -> list[DevicePointResponse]:
        """Every point called `name` on the given devices (default: all the site's devices)."""
        return [
            point
            for device in (self.devices if devices is None else devices)
            for point in (
                device.points.standardized + device.points.native + device.points.virtual
            )
            if point.name == name
        ]


# --- Discovery (GET /site-functions/site/{site_id}) --------------------------------------


class SiteEndpointInfo(BaseModel):
    name: str = Field(..., description="Function name, the last URL segment; starts with its kind")
    kind: FunctionKind = Field(
        ...,
        description="common/site: /site/{site_id}/{name}; device: /site/{site_id}/device/{device_id}/{name}",
    )
    method: Literal["GET"]
    summary: str


class SiteEndpointsResponse(BaseModel):
    site_id: int
    profile: str | None = Field(..., description="The site's profile key; null if the site has no profile (then no endpoints)")
    endpoints: list[SiteEndpointInfo] = Field(default_factory=list, description="Endpoints declared in the site's profile.py")


# --- common: energy-summary --------------------------------------------------------------


class DeviceEnergy(BaseModel):
    device_id: int
    device_name: str
    point_id: int = Field(..., description="The power point that was integrated")
    sample_count: int
    energy_kwh: float


class EnergySummaryResult(BaseModel):
    site_id: int
    start_time: datetime
    end_time: datetime
    energy_kwh: float = Field(..., description="Sum over devices")
    devices: list[DeviceEnergy] = Field(default_factory=list)


# --- common calculation: BESS power statistics ---------------------------------------------

BessPowerSignConvention = Literal["positive_is_discharge", "positive_is_charge"]
"""How a BESS reports the sign of its power. The statistics are always + discharge / - charge."""


class BessPowerStats(BaseModel):
    """Power statistics of one BESS over a window, in kW, as + discharge / - charge."""

    sample_count: int = Field(..., description="Non-null samples the statistics are computed from")
    peak_kw: float | None = Field(
        ..., description="Largest magnitude, charging or discharging (>= 0)"
    )
    average_kw: float | None = Field(
        ..., description="Time-weighted mean: net energy / covered duration"
    )
    max_kw: float | None = Field(..., description="Highest value: the strongest discharge")
    min_kw: float | None = Field(..., description="Lowest value: the strongest charge (negative)")


# --- common calculation: PV power statistics -----------------------------------------------

PvPowerSignConvention = Literal["positive_is_production", "positive_is_consumption"]
"""How a PV point reports the sign of its power. The statistics are always + production."""


class PvPowerStats(BaseModel):
    """Power and energy statistics of one PV power point over a window, in kW / kWh, + production."""

    sample_count: int = Field(..., description="Non-null samples the statistics are computed from")
    energy_produced_kwh: float = Field(..., description="Integral of max(P, 0)")
    energy_consumed_kwh: float = Field(
        ..., description="Integral of max(-P, 0): the inverter's standby draw, mostly at night"
    )
    peak_kw: float | None = Field(
        ..., description="Highest power; for PV the peak and the maximum are the same"
    )
    average_kw: float | None = Field(
        ..., description="Time-weighted mean over the whole window, night included"
    )
    min_kw: float | None = Field(
        ..., description="Lowest power over the whole window: 0, or the standby draw at night"
    )
    producing_threshold_kw: float = Field(
        ..., description="Power at or above which the plant counts as producing"
    )
    producing_hours: float = Field(
        ..., description="Time between consecutive samples both at or above the threshold"
    )
    average_producing_kw: float | None = Field(
        ..., description="Time-weighted mean over producing_hours; None when there are none"
    )
    min_producing_kw: float | None = Field(
        ..., description="Lowest sample at or above the threshold; None when there is none"
    )


# --- common: three-phase imbalance ---------------------------------------------------------

PhaseQuantity = Literal["voltage", "current", "power"]

PhaseImbalanceStatus = Literal["ok", "below_threshold"]
"""below_threshold: |mean| is under the caller's min_mean, so a % would be noise (or a dead bus)."""


class PhaseImbalanceSample(BaseModel):
    """The three phases at one timestamp and their imbalance (NEMA MG-1 definition)."""

    time: datetime
    phase_a: float
    phase_b: float
    phase_c: float
    mean: float = Field(..., description="Mean of the three phases, in the points' unit")
    spread: float = Field(..., description="max - min of the three phases, in the points' unit")
    imbalance_pct: float | None = Field(
        ..., description="max |phase - mean| / |mean| * 100; None when status is below_threshold"
    )
    status: PhaseImbalanceStatus


class PhaseImbalanceTimeseries(BaseModel):
    """The imbalance of one device's three phase points at every timestamp all three were read."""

    quantity: PhaseQuantity
    device_id: int
    unit: str | None = Field(
        ..., description="Shared unit of the three points (and of mean, spread, min_mean)"
    )
    min_mean: float = Field(..., description="|mean| below this gives status below_threshold")
    phase_point_ids: tuple[int, int, int] = Field(..., description="Point ids of phases A, B and C")
    samples: list[PhaseImbalanceSample] = Field(default_factory=list, description="Oldest first")


# --- common: BESS round trip efficiency ----------------------------------------------------

RoundTripBoundary = Literal["dc", "ac", "system"]
"""Where energy is measured: battery terminals, inverter AC side, or the POI with auxiliaries."""

RoundTripStatus = Literal[
    "ok",
    "above_100_percent",  # computed, but physically impossible: check SoC accuracy and points
    "insufficient_throughput",  # charged energy under min_charged_kwh: the ratio would be noise
    "soc_change_too_large",  # |SoC change| over max_soc_change_pct: the correction would dominate
    "missing_soc_data",  # fewer than two SoC readings in the window
]


class RoundTripPowerSource(BaseModel):
    """Energy from one net power point at the boundary, split into charge and discharge by sign."""

    kind: Literal["power"] = "power"
    power_point: DevicePointResponse
    sign_convention: BessPowerSignConvention = "positive_is_discharge"


class RoundTripCounterSource(BaseModel):
    """Energy from two cumulative counters: energy charged and energy discharged."""

    kind: Literal["counters"] = "counters"
    charged_counter_point: DevicePointResponse
    discharged_counter_point: DevicePointResponse
    counter_rollover: float | None = Field(
        None, gt=0, description="Value the counters wrap at, in their unit; None if they never wrap"
    )


class RoundTripEfficiencySettings(BaseModel):
    """What a site declares once per BESS for its round trip efficiency."""

    model_config = ConfigDict(frozen=True)

    usable_energy_kwh: float = Field(
        ..., gt=0, description="Energy a 0 -> 100 % SoC swing represents, battery side"
    )
    boundary: RoundTripBoundary
    min_charged_kwh: float = Field(
        ..., gt=0, description="Less charged energy than this gives insufficient_throughput"
    )
    max_soc_change_pct: float = Field(
        ..., gt=0, le=100, description="A larger |SoC end - SoC start| gives soc_change_too_large"
    )


class RoundTripEfficiencyResult(BaseModel):
    """Round trip efficiency of one BESS over a window, and the terms it was computed from."""

    boundary: RoundTripBoundary
    energy_source: Literal["power", "counters"]
    status: RoundTripStatus
    round_trip_efficiency_pct: float | None = Field(
        ..., description="Set when status is ok or above_100_percent, else None"
    )
    method: Literal["closed_cycle", "soc_corrected"] | None = Field(
        ..., description="closed_cycle when SoC ended where it started; None when not computed"
    )
    charged_kwh: float = Field(..., description="Energy in (E_ch)")
    discharged_kwh: float = Field(..., description="Energy out (E_dis)")
    aux_kwh: float | None = Field(
        ..., description="Auxiliary energy added to E_ch (system boundary only)"
    )
    soc_start_pct: float | None
    soc_end_pct: float | None
    stored_energy_change_kwh: float | None = Field(
        ..., description="Delta S = (SoC end - start) / 100 * usable"
    )


# --- Profile alarms ------------------------------------------------------------------------


class AlarmContext(SiteContext):
    """What a profile alarm's check gets: the site, its devices and points, and the evaluation time."""

    now: datetime = Field(..., description="When this evaluation runs (UTC)")


class AlarmCheck(BaseModel):
    """A profile alarm's verdict for one evaluation: active or not, and what it is about."""

    active: bool
    value: float | None = Field(None, description="The value that decided it, recorded when the alarm raises")
    device_id: int | None = Field(None, description="The device the alarm is about; None for a site-level alarm")


# --- Device health (SLD info boxes) ------------------------------------------------------


class DeviceHealthContext(SiteContext):
    """What a profile's device health check gets: the site, its devices and points, the device
    to judge (`device`, always set) and the evaluation time."""

    device: DeviceWithPoints = Field(..., description="The device to judge")
    now: datetime = Field(..., description="When this check runs (UTC)")

