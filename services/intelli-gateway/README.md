# intelli-gateway

The AI helper for site engineers. An engineer asks a question about one generation site, and
Claude answers it by calling read-only tools, then gives a hint about the likely issue and the
checks to make.

**Status:** the service runs on fictional in-memory sites (`USE_FAKE_DATA=true`). Next, site data
comes from backend-ot over HTTP (all of it in `services/backend_ot/`), and engineer knowledge
moves to the service's own Postgres.

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
| `get_weather_forecast` | only when `EXTERNAL_API_URL` is set |

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

**Auth placeholder.** The service reads the dev headers `X-User-Id`, `X-Roles` and
`X-Site-Ids` (comma-separated site ids). With no headers, it falls back to a dev user who can
access every site. Real OIDC/JWT validation replaces `api/dependencies.py::get_request_context` later,
and nothing else changes.

## Test

```sh
make -C services/intelli-gateway lint typecheck test   # no network, no Docker; Claude is faked
make -C services/intelli-gateway test-integration      # real Claude API: costs tokens, needs a key
```

## Layout (`src/intelli_gateway/`)

The same layout as backend-ot: Pydantic models in `schemas/`, external systems in `services/`,
routers in `api/routers/`, cross-cutting helpers in `utils/`. Feature folders hold functions only.

| Path | Contents |
|---|---|
| `app.py`, `config.py`, `contract.py`, `wiring.py` | App factory, settings (the only place config is read), OpenAPI contract rendering, and the object graph built from settings. |
| `api/` | `routers/` (`health`, `sites`, `tools`), `middleware/request_id.py`, and `dependencies.py` (the auth placeholder). No business logic. |
| `schemas/` | Every data shape: `api_models/` (request and response bodies), `site_data.py`, `knowledge.py` (point guides), `tools.py`, `agent.py`, `context.py`, `forecast.py`. |
| `interfaces/` | The Protocols the code depends on: `site_data`, `knowledge_store`, `tool_provider`, `llm_client`, `conversation_store`. |
| `services/` | Clients for external systems: `claude/client.py` (the only module that imports `anthropic`), `forecast/client.py`, and `backend_ot/` next. |
| `agent/` | `loop.py` (the tool-use loop), `service.py` (what the routers call), `conversations.py` (in-memory store). |
| `tools/` | The tools (`site_tools`, `alarm_tools`, `knowledge_tools`, `external_tools`; `catalog.py` builds them all), the `@tool` decorator, `LocalToolProvider`, `CompositeToolProvider`, authz and output bounds. |
| `knowledge/` | Builds a site's knowledge text and tracks its size (`loader.py`); decides which guide entries apply to a reading (`guides.py`). |
| `prompts/` | The system prompt templates. |
| `fake_data/` | Everything fake: the fake data's shapes (`models.py`), the fictional sites (`sites.py`), the fake site data connector with its plant model (`site_data.py`) and the in-memory knowledge store (`knowledge_store.py`). |
| `utils/` | `logger.py` (JSON logs with request_id), `exceptions.py`, `telemetry.py` (OpenTelemetry hook). |
