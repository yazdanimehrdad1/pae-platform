# intelli-gateway

The AI helper for site engineers. An engineer asks a question about one generation site, and
Claude answers it by calling read-only tools, then gives a hint about the likely issue and the
checks to make. It also provides the platform's **PV forecast** (per site, 15-minute, 72 h,
refreshed every 15 minutes) with a replaceable weather/irradiance source; see
[src/intelli_gateway/solar_forecast/README.md](src/intelli_gateway/solar_forecast/README.md).

**Status:**
- **No fake data at runtime:** site data always comes from backend-ot at `BACKEND_OT_URL` (every
  call is in `services/backend_ot/`), and storage is always the service's own Postgres
  (`DATABASE_URL` is required). Fictional sites exist only in the tests (`tests/doubles/`).
- Engineer knowledge is empty until it moves to the service's own Postgres (next step).
- **Site profiles** (always on): the AI sees a site only after a site admin
  approved its profile, the gateway's copy of the site's facts (site, devices, points,
  topology; never network or Modbus details), and only its approved devices and points. A job
  reads backend-ot every 15 minutes; differences wait as pending changes until approved (admin
  API below, or `python -m intelli_gateway.manage_site_profiles`). See
  [docs/KNOWLEDGE_PLAN.md](docs/KNOWLEDGE_PLAN.md).

Point names are qualified with their device, `DEVICE.point` (e.g. `INV2.active_power`), because
backend-ot point names are only unique within a device.

## What the agent knows

| Kind | Where it comes from | Examples |
|---|---|---|
| Site data | backend-ot, approved devices and points only | sites, devices, topology, point catalog with enum/bit labels, latest values, history, alarm events, active alarm points, last reading time |
| Engineer knowledge | this service (empty until its Postgres store, plan step 2) | point guides: what a point means, normal range, limits, and for each state, alarm bit or vendor fault code its message, severity, probable causes, checks, related points and safety note |
| Reference text | this service | manuals, device IM scripts, experience notes (sent in the cached system prompt) |

Point guides are keyed per site device: (site_id, device_id, point name).

## Tools

| Tool | Use |
|---|---|
| `get_site_overview` | devices, topology, which devices stopped reporting, active alarm count |
| `get_active_alarms` | active alarm events and alarm points with their set bits or fault codes |
| `get_alarm_history` | raise/clear timeline with durations, optionally for one device |
| `get_device_status` | one device: comms, current values with labels, active alarms, guide entries that apply now |
| `list_points` | point catalog: class, labels, whether a guide exists |
| `get_point_values` | latest values of up to 20 points, with labels, active bits, age and a stale flag |
| `get_point_history` | measurements summarized; status and alarm points as a list of changes |
| `explain_point` | the engineer guide for a point plus what applies to its current value |
| `lookup_fault` | one state, alarm bit or vendor fault code: causes, checks, safety note |
| `get_device_script` | a device's IM script (register mapping) |
| `search_experience_notes` | past incidents, by keyword, point or device |
| `get_pv_forecast` | the stored PV forecast, hourly from now: AC kW and the weather behind it (when `FORECAST_ENABLED`) |

The tests' fictional sites (`tests/doubles/sites.py`, never used at runtime) are built to be
diagnosable:
- **Sunfield (site 1):** INV2's cabinet runs hot. Late morning to evening it derates to 1500 kW, its alarm word sets OVER_TEMP, and an over-temperature alarm is raised each day. There is also a past WS1 comms loss.
- **Windridge (site 2):** WTG2 stopped reporting three hours ago, with an active comms alarm.

## Setup

```sh
make -C services/intelli-gateway install   # uv sync
cp services/intelli-gateway/.env.example services/intelli-gateway/.env
# then set ANTHROPIC_API_KEY in that .env (it is never committed)
```

## Run

```sh
make up                                    # repo root: the whole platform, the default
make -C services/intelli-gateway run       # host, --reload: needs DATABASE_URL and a backend-ot
                                           # (the dev stack's Postgres on 5437, backend-ot on 8000)
```

A site is available to the AI only once it is onboarded (approve its profile):

```sh
docker compose -p pae-dev exec intelli-gateway python -m intelli_gateway.manage_site_profiles sync --site 1001
docker compose -p pae-dev exec intelli-gateway python -m intelli_gateway.manage_site_profiles approve --site 1001 --by admin@plusdas.local
```

Then, logged in (session cookie) or with `AUTH_DEV_HEADERS=true`:

```sh
curl localhost:8030/api/v1/sites
curl -X POST localhost:8030/api/v1/sites/1001/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "Are there any active alarms, and what should I check?"}'
```

To continue a conversation, send back the `conversation_id` from the response.
Conversations live in memory and are lost on restart.

## API (`contracts/openapi/intelli-gateway.openapi.json`)

| Route | What it does |
|---|---|
| `POST /api/v1/sites/{site_id}/ask` | Body: `{"question": str, "conversation_id": str or null}`. Returns the answer, the tool calls (name, args, result summary, duration), the stop reason, the iteration count, and token usage including cache read/write tokens. |
| `GET /api/v1/sites` | The sites the caller can access. |
| `GET /api/v1/tools` | The tool specs Claude sees. It mirrors MCP `list_tools` and is meant for debugging. |
| `GET /api/healthz` | Liveness check. |
| `GET /api/v1/sites/{site_id}/forecast/series?start=&end=` | The PV forecast over a window: per 15-minute interval the site's AC kW, each PV device's AC kW, and the weather (GHI, air temperature, wind, cloud cover). Each interval comes from the newest forecast issued at or before its start (past = what was forecast then, future = latest). Used by the web-plusdas Historian. |
| `GET /api/v1/forecast/health` | Active provider, fallbacks, last attempt and success per site. |
| `POST /api/v1/forecast/refresh` | Fetch new forecasts now (`?site_id=` for one site). Needs the `admin` role. |
| `GET /api/v1/site-profiles` | Admin: every synced or onboarded site, its approved version and pending change count. `POST /api/v1/site-profiles/sync` reads every site from backend-ot now. |
| `GET /api/v1/sites/{site_id}/profile` | Admin: the approved profile (what the AI knows of the site's facts). `.../profile/versions` lists every approved version. |
| `GET /api/v1/sites/{site_id}/profile/changes` | Admin: differences between backend-ot (as last read) and the approved profile, each with a `change_id`. `POST .../profile/sync` reads backend-ot now. |
| `POST /api/v1/sites/{site_id}/profile/approve` | Admin: `{"change_ids": [...] (omit for all), "fetched_at": the read you reviewed}`. Creates the next version; the first one onboards the site and must include `site`. 409 when backend-ot was read again since. |

Forecast responses carry `provider`, `units` and `interval_convention` (values are means over
`[interval_start, interval_end)`, times UTC).

**Auth placeholder.** The service reads the dev headers `X-User-Id`, `X-Roles` and
`X-Site-Ids` (comma-separated site ids). With no headers, it falls back to a dev user who can
access every site. Real OIDC/JWT validation replaces `api/dependencies.py::get_request_context` later,
and nothing else changes.

## Test

```sh
make -C services/intelli-gateway lint typecheck test   # no network, no Docker; Claude is faked
make -C services/intelli-gateway test-integration      # Postgres tests on a throwaway container
make -C services/intelli-gateway test-llm              # real Claude API: costs tokens, needs a key
```

## Layout (`src/intelli_gateway/`)

The same layout as backend-ot: Pydantic models in `schemas/`, external systems in `services/`,
routers in `api/routers/`, cross-cutting helpers in `utils/`. Feature folders hold functions only.

| Path | Contents |
|---|---|
| `app.py`, `config.py`, `contract.py`, `wiring.py` | App factory, settings (the only place config is read), OpenAPI contract rendering, and the object graph built from settings. |
| `api/` | `routers/` (`health`, `sites`, `tools`, `forecast`), `middleware/request_id.py`, and `dependencies.py` (the auth placeholder). No business logic. |
| `schemas/` | Every data shape: `api_models/` (request and response bodies), `backend_ot/` (backend-ot's responses, strict), `site_data.py`, `knowledge.py` (point guides), `tools.py`, `agent.py`, `context.py`, `solar_forecast.py` (the provider-neutral forecast models), `open_meteo/` (Open-Meteo's wire format). |
| `interfaces/` | The Protocols the code depends on: `site_data`, `knowledge_store`, `tool_provider`, `llm_client`, `conversation_store`, and for the forecast `pv_forecast_source`, `weather_provider`, `pv_model`, `forecast_repository`, `site_config_source`. |
| `services/` | Clients for external systems: `claude/client.py` (the only module that imports `anthropic`), `backend_ot/` (`client.py` for every backend-ot request, `site_data.py` and `site_config.py` mapping it to the agent's and the forecast's shapes), `open_meteo/` and `noaa_hrrr/` (forecast providers; HRRR is a stub), `postgres/` (engine, migrations, forecast repository). |
| `agent/` | `loop.py` (the tool-use loop), `service.py` (what the routers call), `conversations.py` (in-memory store). |
| `site_profile/` | Site profiles: `diff.py` (compare an approved profile with backend-ot, apply approved changes; pure), `service.py` (`SiteProfileService`: sync, pending changes, approve, the AI's approved view), `gate.py` (`ApprovedSiteDataConnector`, the AI's only way to site data), `scheduler.py` (the sync job). |
| `solar_forecast/` | The PV forecast: `ForecastService` (the facade), `weather_model_source.py`, `pv_model.py` (pvlib), `registry.py` (source names), `scheduler.py` (the refresh job). |
| `tools/` | The tools (`site_tools`, `alarm_tools`, `knowledge_tools`, `forecast_tools`; `catalog.py` builds them all), the `@tool` decorator, `LocalToolProvider`, `CompositeToolProvider`, authz and output bounds. |
| `knowledge/` | Builds a site's knowledge text and tracks its size (`loader.py`); decides which guide entries apply to a reading (`guides.py`). |
| `prompts/` | The system prompt templates. |
| (`tests/doubles/`) | Not in the package: the test doubles. Fictional sites (`sites.py`, `models.py`) and their connector with its plant model (`site_data.py`), in-memory stores (users, user data, knowledge, site profiles, forecasts), the forecast fakes (`forecast.py`), and `services.py::build_test_services`, which wires them all. |
| `utils/` | `logger.py` (JSON logs with request_id), `exceptions.py`, `telemetry.py` (OpenTelemetry hook). |
