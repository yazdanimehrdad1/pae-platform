# intelli-gateway

The AI helper for site engineers. An engineer asks a question about one generation site, and
Claude answers it by calling read-only tools, then gives a hint about the likely issue and the
checks to make. It also provides the platform's **PV forecast** (per site, 15-minute, 72 h,
refreshed every 15 minutes) with a replaceable weather/irradiance source; see
[src/intelli_gateway/solar_forecast/README.md](src/intelli_gateway/solar_forecast/README.md).

**Status:**
- `USE_FAKE_DATA=true` (default): fictional in-memory sites with example engineer knowledge.
- `USE_FAKE_DATA=false`: site data from backend-ot at `BACKEND_OT_URL` (every call is in
  `services/backend_ot/`). Engineer knowledge starts empty until it moves to the service's own
  Postgres (next step).

Point names are qualified with their device, `DEVICE.point` (e.g. `INV2.active_power`), because
backend-ot point names are only unique within a device.

## What the agent knows

| Kind | Where it comes from | Examples |
|---|---|---|
| Site data | backend-ot (fake for now) | sites, devices, topology, point catalog with enum/bit labels, latest values, history, alarm events, active alarm points, last reading time |
| Engineer knowledge | this service (in memory for now) | point guides: what a point means, normal range, limits, and for each state, alarm bit or vendor fault code its message, severity, probable causes, checks, related points and safety note |
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
| `get_pv_forecast` | the stored PV forecast, hourly from now: kW, kWh and the weather behind it (when `FORECAST_ENABLED`) |

The fake sites are built to be diagnosable:
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
make -C services/intelli-gateway run       # http://127.0.0.1:8030 (host, --reload)
# or, with the root dev stack down:
make -C services/intelli-gateway up        # container, host port 8030
```

With the whole platform, `make up` at the repo root includes it.

```sh
curl localhost:8030/api/v1/sites
curl localhost:8030/api/v1/tools
curl -X POST localhost:8030/api/v1/sites/1/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "Why is INV2 producing less than INV1?"}'
curl -X POST localhost:8030/api/v1/sites/2/ask \
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
| `GET /api/v1/sites/{site_id}/forecast` | The latest PV forecast over `start`/`end` (ISO 8601 with offset), `resolution` (minutes), `format=json\|csv`. |
| `GET /api/v1/sites/{site_id}/forecast/latest` | The latest PV forecast in full. |
| `GET /api/v1/sites/{site_id}/forecast/summary?date=` | Energy, peak and first/last production for one local day. |
| `GET /api/v1/sites/{site_id}/forecast/raw` | The weather behind the latest forecast (404 for PV-power-only sources). |
| `GET /api/v1/forecast/health` | Active provider, fallbacks, last attempt and success per site. |
| `POST /api/v1/forecast/refresh` | Fetch new forecasts now (`?site_id=` for one site). Needs the `admin` role. |

Forecast responses carry `provider`, `units` and `interval_convention` (values are means over
`[interval_start, interval_end)`, energy summed, times UTC).

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
| `solar_forecast/` | The PV forecast: `ForecastService` (the facade), `weather_model_source.py`, `pv_model.py` (pvlib), `registry.py` (source names), `scheduler.py` (the refresh job). |
| `tools/` | The tools (`site_tools`, `alarm_tools`, `knowledge_tools`, `forecast_tools`; `catalog.py` builds them all), the `@tool` decorator, `LocalToolProvider`, `CompositeToolProvider`, authz and output bounds. |
| `knowledge/` | Builds a site's knowledge text and tracks its size (`loader.py`); decides which guide entries apply to a reading (`guides.py`). |
| `prompts/` | The system prompt templates. |
| `fake_data/` | Everything fake: the fake data's shapes (`models.py`), the fictional sites (`sites.py`), the fake site data connector with its plant model (`site_data.py`) the in-memory knowledge store (`knowledge_store.py`), and the forecast fakes (`forecast.py`: site configs, clear-sky weather, a PV-power source, an in-memory repository). |
| `utils/` | `logger.py` (JSON logs with request_id), `exceptions.py`, `telemetry.py` (OpenTelemetry hook). |
