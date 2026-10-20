"""PvlibPvModel: normalized weather -> PV power, per array and interval (PVWatts-style).

For each array and interval:
1. Solar position at the interval midpoint (pvlib, with the site's elevation).
2. Plane-of-array irradiance: the provider's, if it gave one for this array; otherwise transposed
   from GHI/DNI/DHI (pvlib Hay-Davies).
3. Cell temperature: pvlib SAPM, open rack, glass/polymer modules.
4. DC = dc_capacity_kw * POA / 1000 * (1 + gamma * (T_cell - 25)).
5. AC = DC * (1 - system losses), clipped at ac_capacity_kw; zero at night, never negative.
6. Energy kWh = AC kW * resolution / 60.

Knows nothing about any provider: it only reads WeatherForecast.
"""

from typing import cast

import numpy as np
import pandas as pd
import pvlib

from intelli_gateway.schemas.solar_forecast import (
    PvArrayConfig,
    PVArrayInterval,
    PVInterval,
    SiteConfig,
    WeatherForecast,
)

STC_IRRADIANCE_W_M2 = 1000.0
STC_CELL_TEMP_C = 25.0
SAPM_PARAMETERS = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_polymer"]


class PvlibPvModel:
    def compute(self, site: SiteConfig, weather: WeatherForecast) -> list[PVInterval]:
        intervals = weather.intervals
        if not intervals:
            return []
        hours = weather.resolution_minutes / 60.0
        midpoints = pd.DatetimeIndex(
            [
                interval.interval_start + (interval.interval_end - interval.interval_start) / 2
                for interval in intervals
            ]
        )
        location = site.location
        solar = cast(
            pd.DataFrame,
            pvlib.solarposition.get_solarposition(
                midpoints,
                location.latitude,
                location.longitude,
                altitude=location.elevation_m if location.elevation_m is not None else 0.0,
            ),
        )
        ghi = np.array([interval.ghi for interval in intervals], dtype=float)
        dni = np.array([interval.dni for interval in intervals], dtype=float)
        dhi = np.array([interval.dhi for interval in intervals], dtype=float)
        temp_air = np.array([interval.temp_air_c for interval in intervals], dtype=float)
        wind = np.array([interval.wind_speed_ms for interval in intervals], dtype=float)
        zenith = solar["apparent_zenith"].to_numpy(dtype=float)
        sun_up = zenith < 90.0
        dni_extra = np.asarray(pvlib.irradiance.get_extra_radiation(midpoints), dtype=float)

        per_array: list[list[PVArrayInterval]] = []
        for array in site.arrays:
            poa = _poa(array, weather, ghi, dni, dhi, dni_extra, solar)
            poa = np.where(sun_up, np.clip(poa, 0.0, None), 0.0)
            cell_temp = pvlib.temperature.sapm_cell(poa, temp_air, wind, **SAPM_PARAMETERS)
            gamma = array.temp_coefficient_pct_per_c / 100.0
            dc_kw = (
                array.dc_capacity_kw
                * poa
                / STC_IRRADIANCE_W_M2
                * (1.0 + gamma * (np.asarray(cell_temp, dtype=float) - STC_CELL_TEMP_C))
            )
            dc_kw = np.clip(dc_kw, 0.0, None)
            after_losses = dc_kw * (1.0 - array.system_loss_pct / 100.0)
            ac_kw = np.clip(after_losses, 0.0, array.ac_capacity_kw)
            per_array.append(
                [
                    PVArrayInterval(
                        array_id=array.array_id,
                        poa=float(poa[index]),
                        cell_temp_c=float(np.asarray(cell_temp)[index]),
                        pv_dc_kw=float(dc_kw[index]),
                        pv_ac_kw=float(ac_kw[index]),
                        pv_energy_kwh=float(ac_kw[index]) * hours,
                    )
                    for index in range(len(intervals))
                ]
            )

        result: list[PVInterval] = []
        for index, interval in enumerate(intervals):
            arrays = tuple(array_intervals[index] for array_intervals in per_array)
            result.append(
                PVInterval(
                    interval_start=interval.interval_start,
                    interval_end=interval.interval_end,
                    ghi=interval.ghi,
                    dni=interval.dni,
                    dhi=interval.dhi,
                    temp_air_c=interval.temp_air_c,
                    wind_speed_ms=interval.wind_speed_ms,
                    cloud_cover_pct=interval.cloud_cover_pct,
                    pv_dc_kw=sum(item.pv_dc_kw or 0.0 for item in arrays),
                    pv_ac_kw=sum(item.pv_ac_kw for item in arrays),
                    pv_energy_kwh=sum(item.pv_energy_kwh for item in arrays),
                    arrays=arrays,
                )
            )
        return result


def _poa(
    array: PvArrayConfig,
    weather: WeatherForecast,
    ghi: np.ndarray,
    dni: np.ndarray,
    dhi: np.ndarray,
    dni_extra: np.ndarray,
    solar: pd.DataFrame,
) -> np.ndarray:
    """The provider's POA where it has one for this array, transposed irradiance elsewhere."""
    provided = np.array(
        [interval.poa_by_array.get(array.array_id, np.nan) for interval in weather.intervals],
        dtype=float,
    )
    if not np.isnan(provided).any():
        return provided
    transposed = pvlib.irradiance.get_total_irradiance(
        surface_tilt=array.tilt_deg,
        surface_azimuth=array.azimuth_deg,
        solar_zenith=solar["apparent_zenith"].to_numpy(dtype=float),
        solar_azimuth=solar["azimuth"].to_numpy(dtype=float),
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        dni_extra=dni_extra,
        model="haydavies",
    )["poa_global"]
    transposed = np.nan_to_num(np.asarray(transposed, dtype=float), nan=0.0)
    return np.where(np.isnan(provided), transposed, provided)
