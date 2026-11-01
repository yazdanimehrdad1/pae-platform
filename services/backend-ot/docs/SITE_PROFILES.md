# Site profiles

A **site profile** is one site's own code in backend-ot: the calculations it serves at a URL, the
alarms it raises, how it judges device health in the SLD, and the virtual points it computes and
stores. Everything lives in `src/site_profiles/`. A site uses at most one profile, and a profile
belongs to at most one site. A site with no site-specific code has no profile (`sites.profile` is
NULL); there is no shared default profile.

Contents:

1. [What a profile can declare](#1-what-a-profile-can-declare)
2. [Where things live](#2-where-things-live)
3. [Naming conventions](#3-naming-conventions)
4. [Creating a profile, step by step](#4-creating-a-profile-step-by-step)
5. [How a profile becomes active](#5-how-a-profile-becomes-active)
6. [Changing or removing things later](#6-changing-or-removing-things-later)
7. [Checklist](#7-checklist)

## 1. What a profile can declare

A profile is a `SiteProfile` (`src/site_profiles/declarations/profile.py`) built in the site's
`profile.py`. It is made of declarations, which are frozen Pydantic models with no logic of their
own. Each one points at an `async def` function:

| Declaration | What it gives the site | Function signature | Runs |
|---|---|---|---|
| `SiteEndpoint` (`declarations/endpoint.py`) | A URL under `/api/site-functions` | `async (SiteContext, TimeWindowParams) -> <response_model>` | On request |
| `SiteAlarm` (`declarations/alarm.py`) | A PROFILE alarm row, raised and cleared automatically | `async (AlarmContext) -> AlarmCheck` | Every alarm evaluation cycle |
| `DeviceHealthCheck` (`declarations/health.py`) | A health verdict in the SLD info box of one element type (`bess`, `pv`) | `async (DeviceHealthContext) -> DeviceHealth` | On `GET /api/sites/{site_id}/sld/values` |
| `SiteVirtualPoint` (`declarations/virtual_point.py`) | A VIRTUAL device point whose values are **stored** | `async (VirtualPointContext) -> list[TimestampedValue]` | Every poll interval (job `profile_point_compute`) |

The functions read the site's data through **SPF points** (`declarations/spf_point.py`). An SPF
point names a device point and says how to read it:

```python
SPF_BESS1_ACTIVE_POWER = SpfPoint(
    device="2bess_1pv-bess1",       # the device's name on the site
    point="BESS_ACTIVE_POWER",      # the point's name (the STANDARDIZED one where it exists)
    category="STANDARDIZED",        # NATIVE | STANDARDIZED | VIRTUAL; informational only
    scale=1.0,                      # multiplier to the function's unit (W -> kW: 0.001)
    sign=1,                         # +1 or -1, so the value reads export positive
)
```

Points are referenced **by name, never by id**: names are the same in every environment (local,
dev, prod), ids are not.

### Endpoint fields

```python
SiteEndpoint(
    method="GET",                                  # only GET for now
    kind="site",                                   # common | site | device
    name="site-bess1-rolling-round-trip-efficiency",
    controller=site_bess1_rolling_round_trip_efficiency,
    params_model=RollingRoundTripEfficiencyParams, # TimeWindowParams (default) or a subclass
    response_model=BessRollingRoundTripEfficiencyResult,
    summary="...",                                 # one line for OpenAPI and the discovery endpoint
    output="series",                               # scalar (default) | series
    device_types=(),                               # device endpoints only: types it applies to
)
```

- **`kind`** decides the URL and where the controller must live:

  | kind | URL | Controller lives in |
  |---|---|---|
  | `common` | `GET /api/site-functions/site/{site_id}/<name>` | `site_profiles/common/` (shared by every site) |
  | `site` | `GET /api/site-functions/site/{site_id}/<name>` | `site_profiles/individual_sites/<profile key>/` |
  | `device` | `GET /api/site-functions/site/{site_id}/device/{device_id}/<name>` | `site_profiles/individual_sites/<profile key>/` |

- **`params_model`**: every endpoint accepts a window: `time_range` (`1H, 6H, 12H, 1D, 2D, 3D, 1W,
  1M, 3M`), or `start_time` with an optional `end_time`, plus `tz`. For more query parameters,
  subclass `TimeWindowParams` with flat fields. `RollingRoundTripEfficiencyParams` adds
  `lookback_days`, for example.
- **`output="series"`**: the response model must have `series: PointTimeseries` or `series:
  list[PointTimeseries]`. The historian lists series endpoints next to device points, and they
  also accept `max_points` (chart sampling, `src/helpers/sampling/README.md`). Scalar endpoints
  are not shown in the historian. Reports and the API can still use them.
- **`device_types`**: only for `kind="device"`. The UI offers the endpoint only under those
  device types; leave it empty for every device.

## 2. Where things live

All paths are under `services/backend-ot/`. The example is the `powerflow_2bess_1pv` profile.

```
src/site_profiles/
  declarations/                  the shapes (SiteProfile, SiteEndpoint, SiteAlarm, ...); no logic
  common/                        shared by every site
    shared_helper_functions.py   historian read, unit conversion, integration, combining series
    spf_point_functions.py       the SPF pipeline: spf_common_sum_points, spf_common_find_device_point
    shared_health.py
    <device type>/               bess/, pv/, generator/, pa_ied/
      <type>_functions.py        public shared calculations (spf_common_*)
      <type>_helper_functions.py pure helpers behind them
      <type>_health.py           shared health checks
  individual_sites/
    <profile key>/               one package per profile; the directory name IS the profile key
      __init__.py
      profile.py                 the SiteProfile: the only place things are declared
      <key>_points.py            the site's SPF points
      <key>_functions.py         endpoint controllers (site_*, device_*)
      <key>_helper_functions.py  the site's own helpers (optional)
      <key>_alarms.py            alarm checks (optional)
      <key>_health.py            health checks (optional)
      <key>_virtual_points.py    compute functions for stored virtual points (optional)
  profile_registry.py            ALL_SITE_PROFILES + the startup checks

src/schemas/site_profiles/
  common.py                      shared models: TimeWindowParams, SiteContext, common results
  individual_sites/<key>.py      the site's own params and response models

tests/unit/site_profiles/
  common/...                     tests of the common functions
  individual_sites/<key>/        tests of the site's pure logic
  test_profile_registry.py       the list of every registered route
tests/integration/api/routers/
  test_site_functions_<key>.py   the endpoints against a real database
```

### The layers a function goes through

A site controller does no reading or maths of its own beyond wiring:

1. **Site controller** (`<key>_functions.py`): resolves the window, reads its SPF points through
   the pipeline and calls a common function.
2. **SPF pipeline** (`common/spf_point_functions.py`, `spf_common_sum_points`): finds each point
   by device and point name, does one historian read, applies `value × scale × sign`, rounds
   to the poll second and keeps only timestamps where every point has a value. A missing device,
   a missing point, or a STANDARDIZED point not linked to a real one gives a 404 naming it.
3. **Common function** (`common/<type>/<type>_functions.py`): pure. It assumes the series it
   gets are already found, read and sanitized, and does no lookup and no read.

```python
async def round_trip_efficiency(ctx, params, power: SpfPoint, soc: SpfPoint):
    window = params.resolve_window()
    power_kw = await spf_common_sum_points(ctx, (power,), window)   # pipeline
    soc_pct = await spf_common_sum_points(ctx, (soc,), window)
    return BessRoundTripEfficiencyResult(
        ...,
        round_trip=spf_common_bess_round_trip_efficiency(power_kw, soc_pct, BESS_ROUND_TRIP_SETTINGS),
    )
```

`spf_common_sum_points` returns `list[TimestampedValue]`, the same type a stored virtual point's
`compute` returns. The same calculation can therefore serve an endpoint (computed on request,
nothing stored) or a stored VIRTUAL point.

### Import rules

- `site_profiles` must never import `helpers.alarms`, `api` or `scheduler`, even inside a
  function. Those packages import `site_profiles`, so the reverse would be a circular import
  (`tests/unit/site_profiles/test_import_boundaries.py`).
- A site package may import `common/`. `common/` never imports a site package, and one site
  package never imports another.

## 3. Naming conventions

| What | Convention | Example | Enforced by |
|---|---|---|---|
| Profile key | lower-case, `_`-separated, at most 64 chars; **the same as the package directory** | `powerflow_2bess_1pv` | registry (controller module must be `site_profiles.individual_sites.<key>.*`) |
| Profile constant | `<KEY>_PROFILE` in `profile.py` | `POWERFLOW_2BESS_1PV_PROFILE` | convention |
| Site module files | `<key>_points.py`, `<key>_functions.py`, `<key>_helper_functions.py`, `<key>_alarms.py`, `<key>_health.py`, `<key>_virtual_points.py` | `powerflow_2bess_1pv_functions.py` | convention |
| Endpoint name | `<kind>-` plus lower-case words joined by `-` (letters and digits only) | `site-poi-active-power`, `device-inverter-availability`, `common-energy` | registry (startup error) |
| Endpoint controller | the endpoint name in snake_case | `site-poi-active-power` → `site_poi_active_power` | convention |
| Shared helper in a site package | no prefix, plain descriptive name | `power_series`, `round_trip_efficiency`, `rolling_step` | convention |
| Public common function | `spf_common_<name>` | `spf_common_bess_round_trip_efficiency` | convention |
| Private common helper | `_spf_common_<name>`, called only inside its own file | `_spf_common_stored_energy_change_kwh` | convention |
| SPF point constant | `SPF_<DEVICE>_<QUANTITY>` | `SPF_BESS1_STATE_OF_CHARGE` | convention |
| A function's group of SPF points | `SITE_<FUNCTION>` (a tuple) | `SITE_ASSETS_ACTIVE_POWER = (SPF_BESS1_ACTIVE_POWER, ...)` | convention |
| Alarm `key`, virtual point `key` | lower-case words joined by `_`; stable: **renaming makes a new one** | `high_severity_alarm_point_active` | pydantic pattern |
| Site schemas | `src/schemas/site_profiles/individual_sites/<key>.py`; results end in `Result`, params in `Params` | `BessRoundTripEfficiencyResult`, `RollingRoundTripEfficiencyParams` | convention |
| Integration test file | `tests/integration/api/routers/test_site_functions_<key>.py` | `test_site_functions_powerflow_2bess_1pv.py` | convention |

Device and point names in SPF points are the names the site's devices have in the database. For a
powerflow site that is `<site>-<asset>` (`2bess_1pv-bess1`), as the powerflow seed creates them.

## 4. Creating a profile, step by step

The example adds a profile `my_site` with one site endpoint.

### Step 1: create the package

```
src/site_profiles/individual_sites/my_site/__init__.py
src/site_profiles/individual_sites/my_site/my_site_points.py
src/site_profiles/individual_sites/my_site/my_site_functions.py
src/site_profiles/individual_sites/my_site/profile.py
src/schemas/site_profiles/individual_sites/my_site.py
```

The directory name is the profile key. A controller outside
`site_profiles.individual_sites.my_site.*` is rejected when the app starts.

### Step 2: declare the SPF points (`my_site_points.py`)

Declare each device point the functions read, once. Prefer the STANDARDIZED point (for example
`BESS_ACTIVE_POWER`, `BESS_STATE_OF_CHARGE`, `METER_ACTIVE_POWER`); use the NATIVE register name
only where no STANDARDIZED point exists. Set `scale` to convert to the function's unit and `sign`
so the value reads export positive (a charging BESS and an importing POI are negative).

```python
SPF_POI_ACTIVE_POWER = SpfPoint(
    device="my_site-poi_meter", point="METER_ACTIVE_POWER", category="STANDARDIZED", scale=1.0, sign=1
)
SITE_POI_ACTIVE_POWER = (SPF_POI_ACTIVE_POWER,)
```

A STANDARDIZED point must be **linked** to a real point on the device (through the API, or by the
seed), or the endpoint returns a 404 saying it isn't linked.

### Step 3: write the models (`src/schemas/site_profiles/individual_sites/my_site.py`)

```python
class PowerSeriesResult(BaseModel):
    site_id: int
    start_time: datetime
    end_time: datetime
    unit: str
    series: PointTimeseries          # required for output="series"
```

If the endpoint needs extra query parameters, subclass `TimeWindowParams` here with flat fields
(`Field(7, ge=1, le=90)`): they become validated query parameters, and a bad value is a 422.

### Step 4: write the controller (`my_site_functions.py`)

```python
async def site_poi_active_power(ctx: SiteContext, params: TimeWindowParams) -> PowerSeriesResult:
    """The POI meter's active power (kW)."""
    window = params.resolve_window()
    values = await spf_common_sum_points(ctx, SITE_POI_ACTIVE_POWER, window)
    return PowerSeriesResult(
        site_id=ctx.site.site_id,
        start_time=window.display(window.start_time),
        end_time=window.display(window.end_time),
        unit="kW",
        series=spf_common_points_series(values, "POI active power (kW)", "kW"),
    )
```

Rules the registry checks:

- it is `async def`;
- its return annotation is **exactly** the endpoint's `response_model`;
- for a series endpoint, the response model has a `series` field of `PointTimeseries` or
  `list[PointTimeseries]`.

If the calculation is useful to other sites, put it in `common/<device type>/<type>_functions.py`
as a pure `spf_common_*` function that takes the already-read series. The site controller then
only reads and calls it, as in [the layers](#the-layers-a-function-goes-through).

### Step 5: declare it (`profile.py`)

```python
MY_SITE_PROFILE = SiteProfile(
    key="my_site",
    endpoints=(
        SiteEndpoint(
            method="GET",
            kind="site",
            name="site-poi-active-power",
            controller=site_poi_active_power,
            response_model=PowerSeriesResult,
            summary="The POI meter's active power series (kW)",
            output="series",
        ),
    ),
    # alarms=(SiteAlarm(...),), device_health=(DeviceHealthCheck(...),),
    # virtual_points=(SiteVirtualPoint(...),),
)
```

Only what is declared here exists. A function in `my_site_functions.py` that isn't declared gets
no URL.

### Step 6: register it (`src/site_profiles/profile_registry.py`)

```python
from site_profiles.individual_sites.my_site.profile import MY_SITE_PROFILE

ALL_SITE_PROFILES: tuple[SiteProfile, ...] = (ALPHA_SOLAR_PROFILE, POWERFLOW_2BESS_1PV_PROFILE, MY_SITE_PROFILE)
```

### Step 7: test it

- **Unit tests** go in `tests/unit/site_profiles/individual_sites/my_site/`, for the site's pure
  logic (an empty `__init__.py` is needed). Common functions are tested in
  `tests/unit/site_profiles/common/`.
- **`tests/unit/site_profiles/test_profile_registry.py`**: add each new route to
  `test_one_route_per_declared_endpoint`. This test lists every route of every profile, so it
  fails until you do.
- **Integration**: `tests/integration/api/routers/test_site_functions_my_site.py`. Create a site
  with `profile="my_site"`, its devices and points (linking the STANDARDIZED ones), insert
  readings, and call the endpoint. Cover at least:
  - one result checked by hand;
  - the listing (`GET /api/site-functions/site/{site_id}`);
  - a missing or unlinked point (404);
  - a missing window (422).

```bash
make -C services/backend-ot lint test
make -C services/backend-ot test-integration TEST_PATH=tests/integration/api/routers/test_site_functions_my_site.py
```

### Step 8: regenerate the contract and update consumers

Every endpoint is a typed route in the OpenAPI contract, so a new or changed endpoint changes
`contracts/openapi/backend-ot.openapi.json`. The drift test in `make test` fails until it is
regenerated:

```bash
make -C services/backend-ot contract           # regenerate
git diff -- contracts/                         # classify: additive or breaking
make -C services/web-plusdas api-types && make -C services/web-plusdas typecheck
make -C services/mobile-plusdas api-types && make -C services/mobile-plusdas typecheck
git add contracts/ && make contracts-check     # from the repo root
```

A new endpoint is additive. Removing or renaming an endpoint, or changing a field's type, is
breaking and needs a version bump and the owner's OK (the `contracts` skill has the full
procedure).

## 5. How a profile becomes active

Writing and registering the code makes the profile **available**. It is **active** for a site
only once that site's `sites.profile` holds its key.

### 5.1 At app start: validation

Importing `profile_registry.py` builds `SITE_ENDPOINT_ROUTES` and runs every check. A misdeclared
profile **stops the app from starting** (`SiteProfileConfigError`) rather than failing on a
request:

| Check | Applies to |
|---|---|
| Functions are `async def` | every declaration (checked when it is built) |
| Profile keys are unique | profiles |
| Name is `<kind>-` + lower-case words | endpoints |
| `common` controller in `site_profiles/common/`; `site`/`device` controller in `individual_sites/<key>/` | endpoints |
| Return annotation is `response_model` | endpoints |
| Series endpoint has a `series: PointTimeseries` field | endpoints |
| Names unique within a profile | endpoints |
| A name declared by several profiles has the same method, kind, params, response, output and device types | endpoints (e.g. a shared `common-*` one) |
| Function in `common/` or the profile's own package, returning `AlarmCheck` / `DeviceHealth` / `list[TimestampedValue]` | alarms, health checks, virtual points |
| Keys and names unique; at most one health check per SLD element type; `(device_name, point_name)` unique | alarms, health checks, virtual points |
| `device_types` only on device endpoints | endpoints |

The router (`src/api/routers/site_functions.py`) then mounts **one URL per distinct endpoint
name** across all profiles, with its own query and response models. Series endpoints also get
`max_points`.

Still at startup (`src/app.py` lifespan), for every site:

- `sync_all_sites_profile_alarms()` gives each site one PROFILE alarm row per `SiteAlarm` its
  profile declares;
- `sync_all_sites_profile_points()` gives each site one VIRTUAL point per `SiteVirtualPoint`.

Then the scheduler starts the alarm evaluation and `profile_point_compute` jobs.

### 5.2 Assigning the profile to a site

The profile key is set on the site through the API (or by a seed):

```bash
# a new site
curl -X POST http://localhost:8000/api/sites -H "Content-Type: application/json" \
  -d '{"name": "My Site", ..., "profile": "my_site"}'

# an existing site (omit "profile" to keep it; null removes it)
curl -X PUT http://localhost:8000/api/sites/1001 -H "Content-Type: application/json" \
  -d '{"profile": "my_site"}'
```

The site controller (`src/api/controllers/sites.py`) checks two things:

- **`validate_profile_key`**: the key must be registered, or the request is a **400** listing the
  registered profiles;
- **one site per profile**: if another site holds the key (soft-deleted sites included), the
  request is a **409** naming that site.

Then it syncs right away, so nothing waits for a restart:

| Event | Alarm rows synced | Virtual points synced |
|---|---|---|
| Site created | yes | when its devices are created (see below) |
| Site's `profile` changed (`PUT` with `profile`) | yes | yes |
| Device created, renamed or deleted | | yes: the device may be the one a virtual point names |
| App start | yes, every site | yes, every site |

In the dev stack, `make seed-2bess-1pv` creates the powerflow site with its profile from
`PROFILE_BY_SITE` in `tests/seed_db/powerflow_seed.py`. Add a line there to seed a new powerflow
site with its profile.

### 5.3 What "active" means for each declaration

- **Endpoints**: a request is resolved as: site exists → the site's profile → (device endpoints)
  the device on that site → the endpoint the profile declares under that name → its controller,
  with a `SiteContext` (the site, its devices and their points, loaded once per request).
  - `GET /api/site-functions/site/{site_id}` lists the site's endpoints. The historian (series
    only) and reports use it.
  - The URL is mounted for every site, but only a site whose profile declares the endpoint can
    run it. Another site gets a **404** ("not declared for site …" or "site … has no profile").
  - A `sites.profile` value whose code was removed gives a **500** (`SiteProfileConfigError`).
- **Alarms**: each declared `SiteAlarm` becomes an `alarm_definitions` row (source `PROFILE`,
  found by `key`). Its name, severity and message come from code and are read-only in the UI;
  users can only enable it and set its notifications. A new row is enabled only while the site is
  under `MAX_ENABLED_ALARMS`. The evaluation job runs `evaluate` every
  `ALARM_EVALUATION_INTERVAL_SECONDS` and raises or clears the alarm from `AlarmCheck.active`.
  See `docs/ALARMS.md`.
- **Health checks**: `GET /api/sites/{site_id}/sld/values` runs the profile's check for every SLD
  element of that type that is linked to a device, and the info box shows the verdict.
- **Virtual points**: the sync creates (or adopts, by `point_name`) a VIRTUAL point on the
  device named `device_name`. If the site has no such device, the point is skipped and logged.
  - Every poll interval, `profile_point_compute` calls `compute` for the window after the last
    one it stored. It waits `PROFILE_POINT_SETTLE_SECONDS` for the latest poll to settle, starts
    `backfill` back on the first run, and caps each run at `PROFILE_POINT_MAX_WINDOW_SECONDS`.
    It then stores the values in `device_points_readings`.
  - A failing run retries the same window next time.

### 5.4 Locally: seeing it work

```bash
make up svc=backend-ot          # rebuild and restart backend-ot (data volumes kept)
curl "http://localhost:8000/api/site-functions/site/1001"                      # the listing
curl "http://localhost:8000/api/site-functions/site/1001/site-poi-active-power?time_range=1H"
```

Re-seeding is only needed when the site doesn't exist yet or doesn't have the profile. In the
dev and prod clouds a profile change arrives with the deployed image; the site's `profile` is
set there through the API.

## 6. Changing or removing things later

| Change | Effect |
|---|---|
| Add an endpoint | New route; additive contract change; add it to `test_profile_registry.py` |
| Rename or remove an endpoint, or change its params/response | Breaking contract change: version bump and the owner's OK; update the web and mobile consumers |
| Change an alarm's name, severity or message | Refreshed on the row at the next sync (app start or profile change) |
| Rename an alarm `key` | A **new** alarm; the old row is retired (soft-deleted, history kept) |
| Remove an alarm | Its row is retired at the next sync; history kept |
| Rename a virtual point `key` | A **new** point |
| Remove a virtual point | Its row and stored history stay; the job stops computing it |
| Change a virtual point's `compute` | Only new values use it; already stored values are not recomputed |
| Remove a site's profile (`PUT` with `"profile": null`) | Endpoints return 404 for it; its PROFILE alarms retire; its virtual points stop being computed |
| Delete the profile's code while a site still uses it | That site's endpoint calls return 500; clear `sites.profile` first |

## 7. Checklist

- [ ] Package `src/site_profiles/individual_sites/<key>/` whose directory name is the profile key
- [ ] SPF points in `<key>_points.py`, by device and point name, with scale and sign (export positive)
- [ ] Models in `src/schemas/site_profiles/individual_sites/<key>.py` (`series` field for series endpoints)
- [ ] `async def` controllers in `<key>_functions.py`, annotated to return the response model;
      shared maths in `common/` as pure `spf_common_*` functions
- [ ] Declared in `profile.py`; names `<kind>-words-joined-by-dashes`
- [ ] Added to `ALL_SITE_PROFILES` in `profile_registry.py`
- [ ] Tests: unit, `test_profile_registry.py` route list, integration
- [ ] `make -C services/backend-ot contract`, consumers' `api-types` + `typecheck`, `make contracts-check`
- [ ] The site's `profile` set (API or seed), its STANDARDIZED points linked
- [ ] `make up svc=backend-ot`, then the listing and one endpoint checked with curl
