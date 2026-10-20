"""PvlibPvModel: weather -> PV power, provider-agnostic.

Invariant guarded: output is zero at night and never negative; AC is clipped at the array's AC
capacity; hotter cells produce less; POA from the provider is used as given, and is transposed
from GHI/DNI/DHI when missing; arrays are summed into the site total; energy = kW x hours.
"""

from datetime import UTC, datetime, timedelta

import pytest
from forecast_fakes import SITE, TWO_PLANE_SITE

from intelli_gateway.schemas.solar_forecast import (
    PvArrayConfig,
    SiteConfig,
    WeatherForecast,
    WeatherInterval,
)
from intelli_gateway.solar_forecast.pv_model import PvlibPvModel

NOON_UTC = datetime(2026, 6, 15, 19, 0, tzinfo=UTC)  # solar noon in Phoenix
MIDNIGHT_UTC = datetime(2026, 6, 15, 7, 0, tzinfo=UTC)  # local midnight in Phoenix
STEP = timedelta(minutes=15)


def weather(
    start: datetime,
    ghi: float = 900,
    dni: float = 800,
    dhi: float = 100,
    temp: float = 25.0,
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
                wind_speed_ms=1.0,
                poa_by_array=poa or {},
            ),
        ),
    )


def site_with(array: PvArrayConfig) -> SiteConfig:
    return SITE.model_copy(update={"arrays": (array,)})


MODEL = PvlibPvModel()


class TestPvModel:
    def test_night_is_zero_even_with_bogus_irradiance(self) -> None:
        (interval,) = MODEL.compute(SITE, weather(MIDNIGHT_UTC, ghi=500, poa={7: 500}))
        assert interval.pv_ac_kw == 0 and interval.pv_energy_kwh == 0
        assert interval.arrays[0].poa == 0

    def test_never_negative(self) -> None:
        (interval,) = MODEL.compute(SITE, weather(NOON_UTC, poa={7: -50}))
        assert interval.pv_ac_kw == 0
        assert interval.arrays[0].pv_dc_kw == 0

    def test_clipped_at_ac_capacity(self) -> None:
        oversized = SITE.arrays[0].model_copy(update={"dc_capacity_kw": 20_000})
        (interval,) = MODEL.compute(site_with(oversized), weather(NOON_UTC, poa={7: 1000}))
        assert interval.pv_ac_kw == pytest.approx(oversized.ac_capacity_kw)
        assert (interval.pv_dc_kw or 0) > oversized.ac_capacity_kw

    def test_hot_cells_produce_less(self) -> None:
        (cool,) = MODEL.compute(SITE, weather(NOON_UTC, temp=0, poa={7: 600}))
        (hot,) = MODEL.compute(SITE, weather(NOON_UTC, temp=45, poa={7: 600}))
        assert (hot.arrays[0].cell_temp_c or 0) > (cool.arrays[0].cell_temp_c or 0)
        assert hot.pv_ac_kw < cool.pv_ac_kw

    def test_pvwatts_with_provider_poa(self) -> None:
        # 600 W/m2 on a 6500 kW array with T_cell from SAPM, gamma -0.35 %/C, 14 % losses.
        (interval,) = MODEL.compute(SITE, weather(NOON_UTC, poa={7: 600}))
        array = interval.arrays[0]
        assert array.poa == 600
        cell = array.cell_temp_c or 0.0
        expected_dc = 6500 * 0.6 * (1 - 0.0035 * (cell - 25))
        assert array.pv_dc_kw == pytest.approx(expected_dc)
        assert array.pv_ac_kw == pytest.approx(expected_dc * 0.86)
        assert array.pv_energy_kwh == pytest.approx(array.pv_ac_kw / 4)

    def test_poa_is_transposed_when_missing(self) -> None:
        (interval,) = MODEL.compute(SITE, weather(NOON_UTC))
        poa = interval.arrays[0].poa or 0.0
        # A south-facing 25 degree plane near solar noon in summer gets roughly the GHI.
        assert 700 < poa < 1100
        assert interval.pv_ac_kw > 0

    def test_arrays_sum_into_the_site_total(self) -> None:
        (interval,) = MODEL.compute(TWO_PLANE_SITE, weather(NOON_UTC, poa={7: 700, 8: 500}))
        assert [array.array_id for array in interval.arrays] == [7, 8]
        assert interval.pv_ac_kw == pytest.approx(sum(a.pv_ac_kw for a in interval.arrays))
        assert interval.pv_energy_kwh == pytest.approx(interval.pv_ac_kw / 4)
        assert interval.ghi == 900  # site weather carried through

    def test_empty_weather(self) -> None:
        empty = weather(NOON_UTC).model_copy(update={"intervals": ()})
        assert MODEL.compute(SITE, empty) == []
