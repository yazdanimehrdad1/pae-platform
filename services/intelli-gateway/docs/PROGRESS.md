# intelli-gateway: progress and next steps

This is a handover note, so work can pick up where it left off. It was last updated on
2026-10-19. Keep it current: when a step lands, move it from "Next steps" to "Done".

For setup, the API, the tools and the layout, see [README.md](../README.md). For rules and
gotchas, see [CLAUDE.md](../CLAUDE.md).

## What the service is

An engineer asks a question about one generation site. Claude answers it by calling read-only
tools, and gives a hint about the likely issue and the checks to make.

- **Loop:** a hand-written tool-use loop with no agent frameworks.
- **Tool layer:** designed so tools can later move to MCP servers. The agent loop only sees the
  `ToolProvider` Protocol.
- **Claude:** reached only through `services/claude/client.py`. It runs with adaptive thinking,
  prompt caching and refusal fallback.

## Done

### 1. Phase 1: scaffold, agent loop, API on fake data (commit `ff3172a`)
- **Service setup:** created with the `new-service` skill on port 8030. It is registered in the
  root Makefile, the dev stack, the port registry and `contracts/README.md`, and it publishes
  `contracts/openapi/intelli-gateway.openapi.json`.
- **Endpoints:**
  - `POST /api/v1/sites/{site_id}/ask` returns the answer, the tool calls, the token usage
    (including cache tokens) and the stop reason.
  - `GET /api/v1/sites`, `GET /api/v1/tools` and `/api/healthz`.
- **Auth placeholder:** dev headers `X-User-Id`, `X-Roles` and `X-Site-Ids` (marked
  `TODO(auth)`).
- **Conversations:** kept in memory, append-only (thinking blocks are preserved), bound to one
  user and one site.
- **Agent loop safeguards:** an iteration limit, a total timeout, parallel tool calls, refusal
  handling, and closing tool calls left without results.
- **Logs:** structured JSON with `request_id`; every tool call and every Claude call is logged.

### 2. Phase 2a: what the agent needs to know (commit `ff3172a`)
- **Information inventory.** The plan file holds the full table: diagnosis step, what is needed,
  where it comes from, which tool reads it. In short:
  - **backend-ot has the raw facts:** points with labels and class, readings, alarms, health and
    topology.
  - **Engineers must write the meaning:** nothing in the repo has fault meanings, causes or
    checks.
- **Engineer knowledge model, owned by this service and keyed per site device**
  (`schemas/knowledge.py`):
  - `PointGuide`: what the point means, its normal range, its limits, related points.
  - `StateGuide`: for each enum value, alarm bit or vendor fault code, its message, severity,
    meaning, probable causes, checks, related points and safety note.
  - `LimitGuide`: for analog thresholds.
- **Tools (12):**
  - `get_site_overview`, `get_active_alarms`, `get_alarm_history`, `get_device_status`
  - `list_points`, `get_point_values`, `get_point_history` (summaries, or state changes)
  - `explain_point`, `lookup_fault`
  - `get_device_script`, `search_experience_notes`
  - `get_weather_forecast`, only when `EXTERNAL_API_URL` is set
- **Fake data you can diagnose** (`fake_data/`), built on a small plant model:
  - Sunfield (site 1): INV2's cabinet overheats, so it derates, its alarm bit and fault code
    follow, and an over-temperature alarm is raised each day.
  - Windridge (site 2): WTG2 has stopped reporting, with an active comms alarm.
- **Restructure:** the layout now mirrors backend-ot:
  - `schemas/`, `interfaces/`, `services/<system>/`, `api/routers/`, `utils/`, `fake_data/`
  - feature folders (`agent/`, `tools/`, `knowledge/`, `prompts/`) hold functions only

### 3. Date fix and the backend-ot client (staged, **not committed yet**)
- **Date fix:** each question now carries the site's local date, weekday, time and UTC offset,
  plus "yesterday". The model had mislabelled dates near midnight. This adds the `tzdata`
  dependency, which the user approved.
- **backend-ot client:** every backend-ot call lives in `services/backend_ot/`:
  - `client.py` makes the HTTP calls (httpx with tenacity retries and timeouts).
  - `site_data.py` implements `SiteDataConnector`. Point names are `DEVICE.point` (e.g.
    `INV2.active_power`), because backend-ot names are only unique within a device. A site's
    catalog is cached for 60 s.
  - Strict response models (`extra="forbid"`) are in `schemas/backend_ot/responses.py`.
    `tests/test_backend_ot_contract.py` checks them field by field against
    `contracts/openapi/backend-ot.openapi.json`.
- **Errors:** `UpstreamUnavailableError` turns into HTTP 503 at the API, and into an error
  result Claude can read inside a tool call.
- **`USE_FAKE_DATA`:** `false` uses backend-ot. The knowledge store is then **empty**, so the
  fake guides can't attach to a real site with a matching id.
- **Verified against the dev stack's backend-ot (site 1001, "Powerflow 2BESS 1PV"):** 9 devices,
  416 points, labels, live values, history, alarms and comms all mapped correctly. One real
  `/ask` health check ran end to end with no tool errors, at about $0.20 (estimate).

**Checks at this point:** `make lint typecheck test` passes (173 tests) and
`make check-boundaries` is clean. The real-Claude integration test
(`make test-integration`) has not been run.

## Decisions made with the user (don't change without asking)
- **Engineer knowledge lives in this service** (in memory now, its own Postgres next), not in
  backend-ot. Guides are scoped **per site device**: (site_id, device_id, point name).
- **Every backend-ot call goes in `services/backend_ot/`.**
- **Repo conventions over the original guide:**
  - Python 3.11 and pyright, strict except `api/`, `fake_data/`, `knowledge/`, `prompts/`
  - numbered SQL migrations, not Alembic
  - stdlib JSON logging, not structlog
- **No frameworks:** no LangChain/LangGraph, vector DB, MCP server or queue. Site knowledge is
  sent in full in a cached system block, and a warning is logged above
  `KNOWLEDGE_TOKEN_WARN` tokens.
- **Model:** `claude-opus-5-5`, effort `high`, refusal fallback on (Claude API only).

## Next steps (in order)

1. **Commit the staged work** (step 3 above). Ask the user first.
2. **Engineer knowledge in Postgres:**
   - Add `intelli-gateway-postgres` to `compose.yaml` on host port 5437. Register the port in
     the root `CLAUDE.md`, root `.env.example` and the `run-platform` skill.
   - Use numbered SQL migrations applied at startup with an advisory lock, like powerflow
     (`services/powerflow/src/powerflow/storage/`). Tables: `point_guides` (with states and
     limits as JSONB, or child tables), `knowledge_documents` (manuals, IM scripts, notes).
   - Implement a Postgres `KnowledgeStore` (SQLAlchemy 2 async + asyncpg; both are already used
     by powerflow, but ask before adding them). Add a seed target that loads the Pydantic fake
     knowledge, and a `test-integration` against a throwaway Postgres, like powerflow's
     `compose.test.yaml`.
   - Decide with the user how real-site knowledge gets in at first: a seed module per site, or
     only through the authoring API (step 3).
3. **Authoring API for engineers:** CRUD on point guides and experience notes, under
   `/api/v1/sites/{site_id}/...`. It is additive to this service's contract, so regenerate it
   with `make contract`. Later a web-plusdas page could use it, but web-plusdas currently only
   proxies `/api` and `/powerflow-api`, so that needs a design decision first.
4. **Run the real-Claude integration test** (`make test-integration`) and keep it passing. It
   checks tool use and a cache read on the follow-up question.
5. **Cut token use** (deferred on purpose):
   - Long backend-ot device names make long point names; consider short aliases.
   - `get_device_status` on devices with about 50 points produces big results; add a filter, or
     return only status and alarm points by default.
   - Measure first: the real health check wrote about 29k tokens to the cache.

## Known issues and gaps
- **Mode flags look like alarms.** backend-ot's powerflow seed marks every bitfield as an ALARM
  point, so `DERMode` shows up as an "active alarm". Claude explains it correctly, but it is
  noise. This is logged in `TODO_MONOREPO_TASKS.md` and is a backend-ot change.
- **backend-ot gaps the client works around:**
  - no point descriptions (the engineer guides cover meaning)
  - no stored data quality and no poll history (a device's last reading time stands in for comms
    health)
  - no min/max/avg endpoint (history is summarized on the client)
- **The dev-stack container still uses fake data.** The local `.env` has `USE_FAKE_DATA=true`.
  To use real data there, set it to `false` and recreate the container:
  `docker compose -f deploy/compose/dev.yaml up -d --force-recreate intelli-gateway`.
- **Conversations are lost on restart,** and concurrent requests to the same conversation are
  not serialized.
- **Not built yet:**
  - real authentication (OIDC/JWT), which only needs to replace
    `api/dependencies.py::get_request_context`
  - OpenTelemetry (`utils/telemetry.py` is a no-op hook)
  - tools that perform actions; any such tool needs explicit human approval

## Useful commands

```sh
make -C services/intelli-gateway lint typecheck test       # fake data, scripted Claude, no network
make -C services/intelli-gateway test-integration          # real Claude API (costs tokens)
make -C services/intelli-gateway contract                  # after any API change
make check-boundaries                                      # repo-wide boundary check
# ask a question (dev stack running, ANTHROPIC_API_KEY in the service .env)
curl -X POST localhost:8030/api/v1/sites/1/ask -H 'Content-Type: application/json' \
  -d '{"question": "Why is INV2 producing less than INV1?"}'
```
