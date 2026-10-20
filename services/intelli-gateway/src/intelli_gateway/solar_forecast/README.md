# PV forecast

Per-site PV power forecasts: 15-minute intervals, 72 hours ahead by default, refreshed every
15 minutes and stored with full history (for backtesting). The weather/irradiance source is
replaceable. If Open-Meteo goes away, you add one source and change config. The endpoints, the
PV model, storage and the facade stay as they are.

Weather data by Open-Meteo.com (CC BY 4.0).

## Layering

```
api/routers/forecast.py, tools/forecast_tools.py
        │  call only ForecastService and use the models in schemas/solar_forecast.py
        ▼
solar_forecast/service.py  ForecastService (the facade)
        │  depends only on Protocols:
        ├── interfaces/site_config_source.py   ← services/backend_ot/site_config.py | fake_data
        ├── interfaces/pv_forecast_source.py   ← solar_forecast/weather_model_source.py
        │                                         (= interfaces/weather_provider.py ← services/<provider>/provider.py
        │                                          + interfaces/pv_model.py ← solar_forecast/pv_model.py)
        │                                       ← services/<pv-power-api>/source.py (returns kW directly)
        └── interfaces/forecast_repository.py  ← services/postgres/forecast_repository.py | fake_data
```

Rules:
1. Routers and tools use `ForecastService` and the public models only. They never import a
   provider, pvlib, httpx or a provider's response format.
2. Only `services/<provider>/` (and its wire-format models in `schemas/<provider>/`) knows that
   provider's URL, parameters, field names, units, conventions and errors.
3. Every source returns the same normalized model, so everything downstream doesn't care where
   the data came from.
4. The PV model and storage depend on the normalized models only, never on a provider.
5. The pieces work without the app: build a source and call it from a script or notebook (see
   below).

## Two kinds of source, one seam

`ForecastService` knows one Protocol, `PvForecastSource.forecast(site, horizon_hours,
resolution_minutes) -> PVForecast`. There are two kinds:

| Kind | Example | What it is |
|---|---|---|
| `weather_model` | Open-Meteo, NOAA HRRR, self-hosted Open-Meteo | A `WeatherProvider` (irradiance + temperature + wind) plus `PvlibPvModel`, combined by `WeatherModelSource` |
| `pv_power` | Solcast, Solargis PV output, a vendor's forecast | A source that predicts PV power itself; no weather, possibly no per-array breakdown |

## Normalized data (`schemas/solar_forecast.py`)

- **Times:** timezone-aware, stored in UTC. An interval is `[interval_start, interval_end)`.
- **Values:** the mean over the interval; energy (kWh) is the sum.
- **Units:** irradiance W/m², temperatures °C, wind m/s, power kW, energy kWh, cloud %.
- **Azimuth:** degrees clockwise from north (180 = south, 90 = east). **Tilt:** degrees from
  horizontal. Each provider converts to its own convention.
- `SiteConfig`: site id, name, IANA timezone, `ForecastLocation` (lat, lon, elevation) and
  `PvArrayConfig`s. One array per PV/INVERTER device in backend-ot, with tilt, azimuth, DC kW,
  AC kW, system loss % and temperature coefficient %/°C.
- `WeatherForecast` / `WeatherInterval`: GHI, DNI, DHI, air temperature, wind, optional cloud
  cover, optional POA per array.
- `PVForecast` / `PVInterval`: site totals (`pv_ac_kw`, `pv_energy_kwh`, optional `pv_dc_kw`),
  the weather fields (None for `pv_power` sources) and the per-array breakdown (empty when the
  source predicts the site total only).

## PV model (`pv_model.py`, PVWatts-style)

For each array and interval:
- solar position at the midpoint;
- POA from the provider, or pvlib Hay-Davies transposition when it's missing;
- SAPM cell temperature (open rack, glass/polymer);
- `DC = dc_kW · POA/1000 · (1 + γ·(T_cell − 25))`;
- `AC = DC · (1 − losses)`, clipped at `ac_kW`; zero at night, never negative;
- `kWh = kW · minutes/60`.

The model sits behind `interfaces/pv_model.py`, so it can be swapped too.

## Config (`config.py`, environment)

| Setting | Default | Meaning |
|---|---|---|
| `FORECAST_ENABLED` | `true` | `false`: no fetching (stored forecasts are still served) |
| `FORECAST_SOURCE` | `open_meteo` | Primary source (`registry.py` names) |
| `FORECAST_FALLBACK_SOURCES` | empty | Comma-separated, tried in order when the primary fails |
| `FORECAST_HORIZON_HOURS` | `72` | Hours ahead |
| `FORECAST_RESOLUTION_MINUTES` | `15` | `15` or `60` |
| `FORECAST_FETCH_INTERVAL_MINUTES` | `15` | Refresh period; `0` = no job (only `POST /api/v1/forecast/refresh`) |
| `FORECAST_RETENTION_DAYS` | `90` | Runs issued earlier are deleted |
| `OPEN_METEO_BASE_URL` | `https://api.open-meteo.com` | Hosted, commercial (`https://customer-api.open-meteo.com`) or self-hosted |
| `OPEN_METEO_API_KEY` | unset | Sent as `apikey` when set |
| `OPEN_METEO_TIMEOUT_S` / `_RETRIES` / `_MAX_CALLS_PER_MINUTE` | `15` / `3` / `500` | Per request, attempts, rate limit (the free tier allows 600/min and 10,000/day) |
| `DATABASE_URL` | unset | Postgres for history; unset keeps it in memory |

A provider's own settings (`OPEN_METEO_*`, later `SOLCAST_*`, ...) are read only when it is
selected.

**Fallback:**
- Each refresh tries the primary source, then each fallback in order, and stores the first
  success with `fallback_used` set.
- Every attempt is written to `forecast_fetch_log`.
- `/api/v1/forecast/health` shows the active provider, whether a fallback is in use, the last
  error, and per site whether the forecast is stale (no success for 2 refresh periods).

## How to add a provider

**A weather API (needs the PV model):**
1. Add `services/<name>/provider.py` with a class that implements `interfaces/weather_provider.py`.
   It builds the requests, handles auth, rate limiting and retries, and converts to the
   normalized model: UTC, explicit `[start, end)` intervals, SI units, our azimuth convention,
   POA per array if it has one. It raises `ProviderError` for every failure. Put its wire-format
   Pydantic models in `schemas/<name>/`.
2. Add its settings to `config.py` (namespaced: `<NAME>_*`) and to `.env.example`.
3. Register it in `registry.py`: `"<name>": lambda settings, clock:
   WeatherModelSource(<Name>Provider(...), PvlibPvModel())`.
4. Add a `WeatherCase` to `tests/test_forecast_source_contract.py`, with a fake HTTP transport
   and its failure modes. It must pass the shared contract unchanged.
5. Select it: `FORECAST_SOURCE=<name>`, or put it in `FORECAST_FALLBACK_SOURCES`.

**A PV-power API (returns kW itself):**
1. Add `services/<name>/source.py` with a class that implements
   `interfaces/pv_forecast_source.py` and returns a `PVForecast` with
   `source_kind=pv_power`. Leave the weather fields None and `arrays` empty if it only predicts
   the site total. Convert its resolution and interval convention inside the file.
2. Add settings, a registry entry (`"<name>": lambda settings, clock: <Name>Source(...)`), a
   `SourceCase` in the contract test, and select it in config.

Nothing else changes. `fake_data/forecast.py::FakePvPowerSource` is the worked example of a
PV-power source, and `services/noaa_hrrr/provider.py` is the stub for the planned direct HRRR
source.

## Self-hosted Open-Meteo

Run the open-source server (https://github.com/open-meteo/open-meteo, Docker image
`ghcr.io/open-meteo/open-meteo`) with the models you need downloaded, e.g. NCEP HRRR/GFS for
North America. Then set `OPEN_METEO_BASE_URL=http://<host>:8080`. Same API, no rate limit, no
licence restriction. Nothing else changes.

## Licensing

- The **free** Open-Meteo API (`api.open-meteo.com`) is **non-commercial only**. A commercial
  deployment needs a paid plan (an API key on `customer-api.open-meteo.com`) or self-hosting.
  `capabilities().commercial_use_allowed` reports which case you are in.
- Attribution is required: **"Weather data by Open-Meteo.com"** (CC BY 4.0). Show it wherever
  the forecast is displayed.

## Use without the app

```python
import asyncio
from intelli_gateway.schemas.solar_forecast import ForecastLocation, PvArrayConfig, SiteConfig
from intelli_gateway.services.open_meteo.provider import OpenMeteoProvider
from intelli_gateway.solar_forecast.pv_model import PvlibPvModel
from intelli_gateway.solar_forecast.weather_model_source import WeatherModelSource

site = SiteConfig(site_id=1, name="demo", timezone="America/Phoenix",
                  location=ForecastLocation(latitude=33.45, longitude=-112.07, elevation_m=331),
                  arrays=(PvArrayConfig(array_id=1, name="pv", tilt_deg=25, azimuth_deg=180,
                                        dc_capacity_kw=6500, ac_capacity_kw=5000),))
source = WeatherModelSource(OpenMeteoProvider("https://api.open-meteo.com", 15, 3), PvlibPvModel())
forecast = asyncio.run(source.forecast(site, horizon_hours=24, resolution_minutes=15))
```
