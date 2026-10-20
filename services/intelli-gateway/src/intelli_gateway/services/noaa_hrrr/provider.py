"""NoaaHrrrProvider: planned direct NOAA HRRR source, the swap path if Open-Meteo is unavailable.
A stub: it is registered so the path is visible, and fails with ProviderError if selected.

TODO(hrrr), when it is needed:
- Download HRRR sub-hourly (15-min) GRIB2 with Herbie (`herbie-data`; ask before adding it):
  product "subh", fields DSWRF (GHI), VBDSF (direct beam) and VDDSF (diffuse), TMP:2 m and
  UGRD/VGRD:10 m, for each forecast hour up to 18 h (48 h on the 00/06/12/18Z runs).
- Pick the latest complete run (HRRR publishes about 1-2 h after the run time).
- Extract the nearest grid point to the site (HRRR is 3 km, CONUS only: refuse sites outside).
- DSWRF is GHI. HRRR's beam is on a horizontal plane, so DNI = beam / cos(zenith) (guard low sun);
  DHI = diffuse. Wind = hypot(U, V). Temperature K -> degC.
- Sub-hourly fields are 15-min averages ending at the valid time: interval_start = valid - 15 min.
- No POA: leave poa_by_array empty; the PV model transposes GHI/DNI/DHI.
- Cache GRIB files per run; one run serves every site.
"""

from intelli_gateway.schemas.solar_forecast import (
    SiteConfig,
    WeatherForecast,
    WeatherProviderCapabilities,
)
from intelli_gateway.utils.exceptions import ProviderError

NAME = "noaa_hrrr"


class NoaaHrrrProvider:
    @property
    def name(self) -> str:
        return NAME

    def capabilities(self) -> WeatherProviderCapabilities:
        return WeatherProviderCapabilities(
            resolutions_minutes=(15, 60),
            max_horizon_hours=48,
            variables=("ghi", "dni", "dhi", "temp_air_c", "wind_speed_ms"),
            provides_poa=False,
            commercial_use_allowed=True,  # NOAA data is public domain
        )

    async def fetch_forecast(
        self, site: SiteConfig, horizon_hours: int, resolution_minutes: int
    ) -> WeatherForecast:
        del site, horizon_hours, resolution_minutes
        raise ProviderError("noaa_hrrr is not implemented yet (see services/noaa_hrrr/provider.py)")

    async def health_check(self) -> bool:
        return False

    async def aclose(self) -> None:
        return None
