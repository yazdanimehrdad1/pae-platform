"""PvlibPvModel: weather -> PV AC power, provider-agnostic.

Invariant guarded: output is zero at night and never negative; AC is clipped at the array's AC
capacity; hotter weather produces less; the provider's POA is used as given and transposed from
GHI/DNI/DHI when missing; AC follows PVWatts (DC from POA and SAPM cell temperature, minus
losses); arrays are summed into the site total and the site weather is carried through.
"""

from datetime import UTC, datetime, timedelta

import pvlib
import pytest
from forecast_fakes import SITE, TWO_PLANE_SITE

from intelli_gateway.schemas.solar_forecast import (
    PvArrayConfig,
    SiteConfig,
    WeatherForecast,
    WeatherInterval,
)
from intelli_gateway.solar_forecast.pv_model import SAPM_PARAMETERS, PvlibPvModel

NOON_UTC = datetime(2026, 6, 15, 19, 0, tzinfo=UTC)  # solar noon in Phoenix
MIDNIGHT_UTC = datetime(2026, 6, 15, 7, 0, tzinfo=UTC)  # local midnight in Phoenix
STEP = timedelta(minutes=15)


def weather(
    start: datetime,
    ghi: float = 900,
    dni: float = 800,
    dhi: float = 100,
    temp: float = 25.0,
    wind: float = 1.0,
    poa: dict[int, float] | None = None,
) -> WeatherForecast:
    return WeatherForecast(
        site_id=SITE.site_id,
        provider_name="test",
        issued_at=start,
        resolution_minutes=15,
        intervals=(
            WeatherInterval(
                interval_start=start,
                interval_end=start + STEP,
                ghi=ghi,
                dni=dni,
                dhi=dhi,
                temp_air_c=temp,
                wind_speed_ms=wind,
                cloud_cover_pct=20,
                poa_by_array=poa or {},
            ),
        ),
    )


def site_with(array: PvArrayConfig) -> SiteConfig:
    return SITE.model_copy(update={"arrays": (array,)})


def expected_ac(array: PvArrayConfig, poa: float, temp: float, wind: float) -> float:
    cell = float(pvlib.temperature.sapm_cell(poa, temp, wind, **SAPM_PARAMETERS))
    dc = (
        array.dc_capacity_kw
        * poa
        / 1000
        * (1 + array.temp_coefficient_pct_per_c / 100 * (cell - 25))
    )
    return min(max(dc, 0.0) * (1 - array.system_loss_pct / 100), array.ac_capacity_kw)


MODEL = PvlibPvModel()


class TestPvModel:
    def test_night_is_zero_even_with_bogus_irradiance(self) -> None:
        (interval,) = MODEL.compute(SITE, weather(MIDNIGHT_UTC, ghi=500, poa={7: 500}))
        assert interval.pv_ac_kw == 0
        assert interval.arrays[0].pv_ac_kw == 0

    def test_never_negative(self) -> None:
        (interval,) = MODEL.compute(SITE, weather(NOON_UTC, poa={7: -50}))
        assert interval.pv_ac_kw == 0

    def test_clipped_at_ac_capacity(self) -> None:
        oversized = SITE.arrays[0].model_copy(update={"dc_capacity_kw": 20_000})
        (interval,) = MODEL.compute(site_with(oversized), weather(NOON_UTC, poa={7: 1000}))
        assert interval.pv_ac_kw == pytest.approx(oversized.ac_capacity_kw)

    def test_hot_weather_produces_less(self) -> None:
        (cool,) = MODEL.compute(SITE, weather(NOON_UTC, temp=0, poa={7: 600}))
        (hot,) = MODEL.compute(SITE, weather(NOON_UTC, temp=45, poa={7: 600}))
        assert hot.pv_ac_kw < cool.pv_ac_kw

    def test_pvwatts_with_provider_poa(self) -> None:
        (interval,) = MODEL.compute(SITE, weather(NOON_UTC, poa={7: 600}))
        assert interval.pv_ac_kw == pytest.approx(expected_ac(SITE.arrays[0], 600, 25.0, 1.0))

    def test_poa_is_transposed_when_missing(self) -> None:
        (transposed,) = MODEL.compute(SITE, weather(NOON_UTC))
        # A south-facing 25 degree plane near solar noon in summer gets roughly the GHI, so the
        # output lands between what 700 and 1100 W/m2 on the plane would give.
        array = SITE.arrays[0]
        low, high = expected_ac(array, 700, 25.0, 1.0), expected_ac(array, 1100, 25.0, 1.0)
        assert low < transposed.pv_ac_kw <= high

    def test_arrays_sum_into_the_site_total_and_weather_is_kept(self) -> None:
        (interval,) = MODEL.compute(TWO_PLANE_SITE, weather(NOON_UTC, poa={7: 700, 8: 500}))
        assert [array.array_id for array in interval.arrays] == [7, 8]
        assert interval.pv_ac_kw == pytest.approx(sum(a.pv_ac_kw for a in interval.arrays))
        assert (interval.ghi, interval.temp_air_c, interval.wind_speed_ms) == (900, 25.0, 1.0)
        assert interval.cloud_cover_pct == 20

    def test_empty_weather(self) -> None:
        empty = weather(NOON_UTC).model_copy(update={"intervals": ()})
        assert MODEL.compute(SITE, empty) == []
