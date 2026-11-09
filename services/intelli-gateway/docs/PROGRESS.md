# intelli-gateway: progress and next steps

This is a handover note, so work can pick up where it left off. It was last updated on
2026-11-06. Keep it current: when a step lands, move it from "Next steps" to "Done".

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

### 3. Date fix and the backend-ot client (commit `28a2f69`)
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

### 4. PV forecast (2026-10-20)
- **backend-ot (provider first):** `pv_array_configs` (migration 017, one per PV/INVERTER
  device: tilt, azimuth, DC/AC kW, losses, temperature coefficient), `elevation_m` in the site
  coordinates, `GET /api/sites/{id}/pv-arrays` and `GET/PUT/DELETE
  /api/devices/site/{id}/devices/{device_id}/pv-array`. Contract 3.0.0 -> 3.1.0 (additive). The
  powerflow seed puts site 1001 in Phoenix (33.45, -112.07, 331 m, America/Phoenix) with pv1 at
  tilt 25, azimuth 180, 6500 kW DC / 5000 kW AC.
- **This service's Postgres** (port 5437): `services/postgres/` (engine, migration runner with an
  advisory lock, `001_forecasts.sql`: runs, intervals, fetch log). New dependencies, approved:
  `sqlalchemy[asyncio]`, `asyncpg`, `pvlib`.
- **The forecast:** `solar_forecast/` (`ForecastService`, `WeatherModelSource`, `PvlibPvModel`,
  registry, refresh job), `services/open_meteo/` (15-min `minutely_15`, POA per array plane),
  `services/noaa_hrrr/` (stub), endpoints under `/api/v1/.../forecast`, and the agent tool
  `get_pv_forecast` (replaces the example `get_weather_forecast` and `EXTERNAL_API_*`). API
  0.1.0 -> 0.2.0 (additive).
- **Swap path:** a weather API = provider file + registry entry + config; a PV-power API (Solcast,
  Solargis) = source file + registry entry + config. Fallbacks via `FORECAST_FALLBACK_SOURCES`.
- **Simplified (2026-10-21):** three endpoints remain (`/forecast/series`, `/forecast/refresh`,
  `/forecast/health`); only AC power (site + per PV device) and GHI, air temperature, wind and
  cloud cover are stored and served (migration 002 drops the rest); each refresh prunes the older
  runs' rows it supersedes (one forecast per interval); retention 7 days. Cloud cover now comes
  hourly from Open-Meteo on the same request.
- **Tests:** shared provider/source contract suites, the repository contract (in memory and
  Postgres), PV model, facade, endpoints. `make test-integration` is now the Postgres suite;
  the real-Claude test moved to `make test-llm`.

### 5. Deployment readiness (2026-10-24; root `deploy/PLAN.md`, Stage 1)
- `GET /api/readyz`: 200 with `database` `ok` or `not_configured` (no `DATABASE_URL`), 503 with
  `unavailable` when its Postgres doesn't answer (`services/postgres/database.py::database_is_reachable`).
  The production deploy waits on it. Contract change, additive.
- Postgres pinned to `postgres:16.15-alpine` (dev and tests), the same image as prod.
- `DevicePointResponse` gained `source_point_id`, catching up with backend-ot's contract.

### 6. PlusDAS users, step 1: accounts, sessions, login (2026-11-02)
Plan: `~/.claude/plans/we-want-to-work-foamy-kay.md`. This service now owns PlusDAS users.
- **Migration `003_users`:** `users` (lower-case unique email, scrypt hash, role
  engineer | admin | monitor, disabled) and `user_sessions` (SHA-256 of the cookie token only,
  sliding `expires_at`, `last_seen_at`).
- **`auth/`:** `passwords.py` (stdlib `hashlib.scrypt`, per-user salt, no new dependency) and
  `AuthService` (login, authenticate with a sliding 30-day expiry written at most once a
  minute, logout; disabling a user or changing their password ends their sessions). The store is
  `interfaces/user_store.py`: Postgres in `services/postgres/user_store.py`, in memory in
  `fake_data/user_store.py` (no `DATABASE_URL`), both checked by `tests/user_store_contract.py`.
- **API:** `POST /api/v1/auth/login` (sets an HttpOnly, SameSite=Lax, path `/`, Max-Age cookie;
  `Secure` with `SESSION_COOKIE_SECURE`), `POST /api/v1/auth/logout`, `GET /api/v1/me`.
  `get_request_context` takes the user from the cookie. `/me` never accepts the dev headers.
  Contract change, additive.
- **`AUTH_DEV_HEADERS` (default off since step 3):** when on, a request without a cookie uses the `X-*`
  headers or the dev user. Only tests and host experiments turn it on; the cloud needs no setting.
- **Accounts:** `python -m intelli_gateway.manage_users` (create, set-password, disable, enable)
  in the container; root `make create-user EMAIL=... ROLE=...`.
- **Step 2, per-user data (2026-11-02):** migration `004_user_data`
  (`user_preferences` key → JSONB, `user_saved_trends` with the user's order, `user_notes`;
  all `ON DELETE CASCADE` from `users`). `UserDataService` (`user_data/service.py`) over
  `interfaces/user_data_store.py` (Postgres + in memory, one shared contract in
  `tests/user_data_store_contract.py`). Routes under `/api/v1/me`, session only (never the dev
  headers): `preferences` (list, get/put/delete by key, any JSON ≤ 64 KiB, ≤ 100 keys),
  `trends` (list, create, put, delete, `PUT trends/order`; ≤ 50; only the definition: name,
  points, scale, styles), `notes` (list newest first, create (an imported note may keep its
  dates, never future ones), put, delete; ≤ 200). Another user's id is a 404. Contract, additive.
- **Step 3, web-plusdas switch-over (2026-11-02):** a real login page (email +
  password; the mock and its role picker are gone); trends, notes and preferences come from
  `/api/v1/me`; the first login in a browser imports its old localStorage data once; nginx checks
  the session before `/api` and `/powerflow-api` (`auth_request` to `/api/v1/me`, 60 s cache,
  stale answers while this service is down). `AUTH_DEV_HEADERS` now defaults to off.
- **Accounts in the cloud (2026-11-02):** the first admin comes from the secret
  `intelli-gateway-bootstrap-admin-password` (`BOOTSTRAP_ADMIN_PASSWORD`; dev `admin@plusdas.dev`, prod and local `admin@plusdas.local`, created at
  startup only while there are no users); the dev cloud also keeps a `demo@plusdas.dev` engineer (`DEMO_USER_EMAIL`; locally `demo@plusdas.local`) from
  `intelli-gateway-demo-user-password` (`DEMO_USER_PASSWORD`; never in prod). Admins manage
  accounts at `/api/v1/users` (list, add, rename, role, disable, reset password; never their own
  role or disabled state), and everyone changes their own password at `PUT /api/v1/me/password`.
  web-plusdas: the Users page and an Account card in Settings.
- **Sign in with an email address (2026-11-03):** the account name is the email
  (`email`, not `username`, in the API and the `users` table; checked as name@domain.tld, stored
  lower-case; 003_users edited in place since it never left the laptop). Built-in accounts use the
  reserved `.local` domain. The dev stack's compose.yaml sets `BOOTSTRAP_ADMIN_PASSWORD=admin-password`
  and `DEMO_USER_PASSWORD=demo-password`, so `make up` gives `admin@plusdas.local` (on an empty
  database) and `demo@plusdas.local` with no extra step; `seed-demo`, `make seed-demo-user` and
  `ALLOW_DEMO_USER` are gone.
- **Next:** 4. persistent conversations, per-site grants. Before real cloud accounts: login rate
  limiting and HTTPS (`SESSION_COOKIE_SECURE=true`).

### 7. Site profiles: approved site facts and the AI's gate (uncommitted, 2026-11-06)
Step 1 of [KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md).
- **Migration `005_site_profiles`:** `site_profile_versions` (one row per approved version: the
  catalog as JSONB, who and when, the change ids it approved) and `site_catalog_snapshots` (the
  latest read of backend-ot per site). Stores: Postgres and in memory, one shared contract
  (`tests/site_profile_store_contract.py`).
- **The catalog** is site, devices, points and topology in the agent's shapes
  (`schemas/site_data.py`), so no host, port, Modbus address or scan setting is ever copied.
- **`site_profile/`:** `diff.py` (changes keyed `site`, `topology`, `device:<id>`,
  `point:<device_id>:<name>`; a device added or removed carries its points; a rename is one
  device change and points follow the approved device name), `service.py` (sync, pending
  changes, approve with an optional `fetched_at` check, versions), `gate.py`, `scheduler.py`
  (reads backend-ot at startup and every `SITE_PROFILE_SYNC_INTERVAL_MINUTES`, approves nothing).
- **The gate** (`ApprovedSiteDataConnector`): tools and the agent service see only onboarded
  sites and their approved devices and points; live values, history, alarms and comms are cut
  down to them; a value whose definition changed in backend-ot carries
  `definition_pending_review` (the `get_point_values` description tells the model). Always on
  (since item 8 there is no setting to turn it off).
- **Admin API** (session, `admin` role): `/api/v1/site-profiles` (+ `/sync`),
  `/api/v1/sites/{id}/profile` (+ `/versions`, `/changes`, `/sync`, `/approve`). Contract,
  additive (API version unchanged at 0.2.0, as for users); web-plusdas types regenerated.
- **CLI (the code-level way in):** `python -m intelli_gateway.manage_site_profiles status | sync |
  changes | approve --site N --by EMAIL [--change ID ...]`.
- **Effect on the dev stack and the dev cloud:** with backend-ot data the AI serves no site until
  it is onboarded: run `sync` then `approve` for site 1001 (CLI in the container, or the API).
- **Left for later:** PV arrays, alarm definitions and admin-added ratings in the profile (plan
  section 2); "this is a rename of X" re-linking of guides (step 2, once guides exist);
  per-site query limits beyond today's tool bounds.
- **Checks:** `make lint typecheck test` (386 passed), `make test-integration` (38 passed, incl.
  the Postgres store contract), web-plusdas `typecheck`.

### 8. No fake data at runtime (uncommitted, 2026-11-07)
The user's decision: the running service never uses fictional data; tests keep their doubles.
- **Removed from the service:** `USE_FAKE_DATA` and `SITE_PROFILE_GATE` (the gate is always on),
  the fictional sites and their example guides, the `fake` / `fake_pv_power` forecast sources,
  and every in-memory fallback store. `DATABASE_URL` is required: without it startup fails with
  a ConfigurationError (`wiring.py::_database`).
- **Runtime defaults** (`wiring.py`): site data and forecast site configs from backend-ot, users,
  user data, site profiles and forecasts in Postgres, engineer knowledge from
  `knowledge/store.py::EmptyKnowledgeStore` until its Postgres store (plan step 2).
- **App startup:** without injected services, `create_app` builds them in the lifespan, so
  importing the app and rendering the contract need no database.
- **Tests:** `src/intelli_gateway/fake_data/` moved to `tests/doubles/` (never shipped);
  `doubles/services.py::build_test_services` wires them (fictional sites already onboarded).
  `tests/test_wiring.py` guards the runtime wiring. The old ungated "503 from /v1/sites" test is
  gone (with the gate the site list never reaches backend-ot; a sync against a down backend-ot is
  a 503 in `test_site_profiles_api.py`).
- **Config:** `USE_FAKE_DATA` removed from compose.yaml, `.env.example` (DATABASE_URL now set
  there) and the root `.env.example`. `deploy/cloud/compose.yaml` still sets
  `USE_FAKE_DATA=false`: harmless (unknown settings are ignored); remove it with the next
  approved deploy change.
- **`make run` on the host** needs the dev stack's Postgres (5437) and backend-ot (8000).

### 9. Point descriptions, and the AI Site Profiles page (uncommitted, 2026-11-07)
- **Point descriptions:** the backend-ot connector now copies `profile_point_description` (the
  device profile's one-liner) into each point's `description`. Already onboarded sites see it as
  one pending "description" change per point, to approve once.
- **web-plusdas "AI Site Profiles"** (admins; sidebar, `/site-profiles`): every site's AI access,
  pending change count and last read; per site, the pending changes grouped (site, devices,
  points, topology) with checkboxes and "Approve selected" (the first approval must include
  `site`; a 409 refetches), "Read backend-ot now", what the AI knows (devices and their points:
  description, unit, class, severity, states/bits) and the version history. From now on each
  step builds its web-plusdas UI with it.

### 10. Smoke test on the dev stack, and the real-Claude test (2026-11-07)
- **Dev stack:** the gateway starts (`/api/readyz` ok, migration 005 in place); site 1002 ("Powerflow
  2BESS 1PV", 9 devices, 120 points) is onboarded at v1; the AI Site Profiles page works in a real
  browser (headless Chromium: list, pending changes, what the AI knows, history; no page overflow
  at phone width). backend-ot's seeded points carry no `profile_point_description`, so there were no
  description changes to approve.
- **Found and fixed:** (1) at startup both jobs (site profile sync, forecast refresh) ran before
  backend-ot accepted connections and then waited the whole interval (15 min): a failed run now
  retries after 30 s, and "backend-ot unreachable" is a warning, not a traceback (`tests/test_jobs.py`;
  seen live: failed at :22, succeeded at :52). (2) The site page said "Not onboarded" while the profile
  was still loading (regression test added).
- **`make test-llm` passes** (first time it ran): tool use without tool errors, and the follow-up
  question read the prompt cache. The test itself expected a tool named `get_point_value` (it is
  `get_point_values`); fixed. Three paid runs.

### 11. Engineer knowledge in Postgres, draft and publish, and its UI (2026-11-07)
Step 2 of [KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md).
- **What is authored** (`schemas/knowledge.py`): point guides (meaning, unit note, normal range,
  related points, limits, and per enum value / bit / vendor fault code: label, severity, message,
  meaning, causes, checks, safety note), documents (manual, IM script, procedure, experience note;
  pasted text) and device facts (ratings, notes). Guides are kept by (device_id, point name within
  the device), so an approved device rename keeps them.
- **Storage:** migration `006_knowledge`: `site_knowledge_drafts` (one per site, the whole
  knowledge as JSONB, a `revision` that goes up with every save) and `site_knowledge_versions`.
  Stores: Postgres and in memory, one shared contract (`tests/knowledge_authoring_store_contract.py`).
- **`knowledge/`:** `authoring.py` (pure: item keys, diff, revert, validation, coverage),
  `service.py` (`SiteKnowledgeService`: edits, revert, discard, publish, restore, import),
  `published_store.py` (the AI's `KnowledgeStore`: the latest published version, names translated
  to `DEVICE.point` through the approved profile; knowledge about devices no longer approved is
  kept but not served), `search.py`. The tools didn't change. The site block now also lists device
  ratings and notes; documents gained the `procedure` kind and a `document_id`.
- **Rules on every edit:** approved devices and points only; no credential, private key or IP
  address in any text; one entry per state/bit/code; an edit or publish naming an older
  `draft_revision` is a 409.
- **Admin API** under `/api/v1/sites/{id}/knowledge` (state, coverage, point-guides, documents,
  device-facts, draft/revert, draft discard, publish, versions, restore). Contract, additive.
- **CLI (the code-level way in):** `python -m intelli_gateway.manage_knowledge status | export |
  import | publish` (export/import a site's knowledge as JSON, kept out of the repo).
- **web-plusdas:** a "Knowledge" tab on each AI Site Profile: point guides (status/alarm points
  first, "only points that need a guide", an editor prefilled with backend-ot's state and bit
  labels, vendor fault codes and limits), documents, device ratings, versions (restore), and
  "Review & publish" (put single changes back, discard, publish).
- **Left for later:** "this is a rename of X" re-linking on a point rename; the gap log (step 7).

### 12. Site functions from backend-ot, approved per site, and their UI (uncommitted, 2026-11-08)
Step 4 of [KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md), option B (user's call, 2026-11-08): the gateway
computes nothing; backend-ot runs its site functions and the gateway decides which the AI may use.
- **backend-ot (provider, contract additive):** two labels on each `SiteEndpoint` in a site's
  `profile.py`: `ai_assistant` (default False: the gateway may use it) and `user_visible` (default
  True: the historian and reports show it; an AI-only function sets False). At least one is True.
  `GET /api/site-functions/site/{id}` lists both plus each function's extra `parameters`.
  Reports offer only `user_visible` functions. The 8 functions of the 2BESS 1PV profile are
  labelled `ai_assistant=True` (still user-visible).
- **web-plusdas historian:** `siteFunctionsApi.list` leaves out `user_visible=false` functions.
- **Gateway:** `SiteCatalog.functions` (only `ai_assistant` ones are copied); a function added,
  removed or changed (summary, kind, output, device types, parameters) is a pending change
  `function:<name>`, approved one by one like a point (also when onboarding). No migration: the
  catalog is JSONB, and profiles approved before this show the functions as pending additions.
  The gate runs only approved functions, a device function only on an approved device of a type
  it applies to, with only declared parameters (required ones present); it sends `max_points`
  only for series. `site_profile/functions.py` checks the window (at most
  `TOOL_HISTORY_MAX_DAYS`) and summarizes each series (count, min, max, avg, first, last,
  `TOOL_HISTORY_SAMPLES` samples). backend-ot's 4xx reach Claude as its own message.
- **Tools (14 now):** `list_site_functions` (with the devices each device function applies to)
  and `run_site_function`. The site block does not list functions (the tool does).
- **Admin API:** `POST /api/v1/sites/{id}/functions/{name}/test-run`: the same path as the tool,
  so the admin sees exactly what Claude gets. Contract additive (new routes and fields, a
  `function` change target).
- **web-plusdas:** pending changes get a "Site functions" group; "What the AI knows" lists the
  approved functions with "Try it" (window, device, parameters, the result as the AI gets it).
- **Verified live (dev stack, site 1002):** the sync showed exactly the 8 labelled functions;
  a test-run before approval was 404; after approving: BESS 1 RTE (scalar), POI active power
  (1,351 samples summarized to 12), rolling RTE with `lookback_days=3`; an unknown parameter is
  a 422 without calling backend-ot. The "Try it" dialog worked in headless Chromium.
- **Not done:** `make test-llm` (paid) with a site-function question.

### 13. Knowledge: site prompts, delete older versions, point guides by device (uncommitted, 2026-11-09)
- **Site prompts** (the user's call): the admin's general information about the site, entered
  step by step as any number of named texts instead of one long prompt. A new knowledge item
  (`SitePrompt`: name, text, position; key `prompt:<id>`) in the same draft → publish; a new one
  goes last, an edit keeps its place. Secrets are refused like everywhere. The AI reads them all,
  in order, first in the cached site block ("About this site"). API
  `POST/PUT/DELETE /api/v1/sites/{id}/knowledge/site-prompts[/{prompt_id}]` (read: the knowledge
  state); version summaries count them. No migration (knowledge is JSONB; old content loads with
  none). Contract additive. web-plusdas: "Site prompt" is the first Knowledge tab: numbered
  steps, each with edit and delete (confirmed), and a form for the next step. No reordering yet.
- `DELETE /api/v1/sites/{id}/knowledge/versions?version=1&version=2` (admin): deletes older
  published versions for good and returns the versions left. The version the AI uses can't be
  deleted (422; the store also never deletes a site's latest), so what the AI knows doesn't
  change and version numbers are never reused. Store contract check added; contract additive.
- web-plusdas Knowledge: Versions tab has checkboxes on the older versions, "Delete selected"
  with a confirm; Point guides tab has a Device column and a device filter.
- Verified live: the refusals (live version 422, unknown 404, none given 422). An actual delete
  was not run on the dev stack, so the local site 1002 versions were kept (covered by unit and
  Postgres integration tests).

### 14. Site prompts link to points, site functions, documents and device ratings (uncommitted, 2026-11-09)
- Each site prompt has optional `links` (`SitePromptLinks`: points as device_id + local point
  name, site function names, document ids, device ids for ratings); empty = not applicable. Kept
  sorted and without repeats. Checked on save: points, functions and devices must be in the
  approved profile, documents in the draft. Deleting a document drops it from every prompt's
  links; a link the approved profile no longer has shows in coverage as `orphaned` (`prompt:<id>`).
- The AI, both directions (the user's call): a `Related: ...` line under each prompt in the
  cached site block (unpublished documents left out), and a `related_prompts` field
  ("Prompt N: name") in explain_point, list_points, get_device_status, get_device_script,
  search_experience_notes, list_site_functions and run_site_function when a prompt links the item.
- API: `links` on the site-prompt create/update body (optional).
- web-plusdas: the prompt form has a "Linked to (optional)" row of four pickers (Points, Site
  functions, Documents, Device ratings: devices that have ratings), selected links show as
  removable badges; each prompt shows its links as badges.

### 15. Site scripts renamed to site prompts everywhere (breaking, contract 0.3.0, uncommitted, 2026-11-09)
- The user's call, to match the UI: `SiteScript*` → `SitePrompt*`, `site_scripts` →
  `site_prompts`, `script_id` → `prompt_id`, item key `script:` → `prompt:`, item kind
  `site_script` → `site_prompt`, routes `/knowledge/site-scripts` → `/knowledge/site-prompts`,
  store method `list_site_prompts`. IM scripts (`get_device_script`, `im_script`) are unrelated
  and unchanged. `API_VERSION` 0.2.0 → 0.3.0; web-plusdas (the only consumer) updated in the
  same change.
- Migration `007_site_prompts` rewrites stored drafts and versions (the list key, each item's id,
  and `script:` change ids); integration test runs it on old-format rows.

## Decisions made with the user (don't change without asking)
- **intelli-gateway owns PlusDAS users** (login, sessions, per-user data) in its own Postgres;
  backend-ot stays data-only. Individual accounts, roles engineer | admin | monitor, no
  self-signup. Session = opaque token in an HttpOnly cookie, only its hash stored.
- **Engineer knowledge lives in this service** (its own Postgres), not in backend-ot. Guides are
  scoped **per site device**: (site_id, device_id, point name within the device).
- **Knowledge authoring (2026-11-07):** admins only write and publish; edits are a draft; a
  publish takes the whole site at once (one version; single drafts can be put back first);
  restore = a new version with an old version's content. Older versions can be deleted
  (2026-11-09), never the one the AI uses.
- **Every backend-ot call goes in `services/backend_ot/`.**
- **Site functions (2026-11-08):** backend-ot computes them (option B). backend-ot labels each
  `ai_assistant` (the gateway may use it) and `user_visible` (shown in the historian); the AI uses
  a labelled function only after the site admin approves it in the site profile. This is the one
  place backend-ot carries something for the AI (the user's call).
- **No fake data at runtime** (2026-11-07): backend-ot and the service's Postgres only; test
  doubles live in `tests/doubles/`.
- **Repo conventions over the original guide:**
  - Python 3.11 and pyright, strict except `api/`, `knowledge/`, `prompts/`
  - numbered SQL migrations, not Alembic
  - stdlib JSON logging, not structlog
- **No frameworks:** no LangChain/LangGraph, vector DB, MCP server or queue. Site knowledge is
  sent in full in a cached system block, and a warning is logged above
  `KNOWLEDGE_TOKEN_WARN` tokens.
- **Model:** `claude-opus-5-5`, effort `high`, refusal fallback on (Claude API only).

## Next steps (in order)

The site knowledge, onboarding and answer-cost plan agreed on 2026-11-06 is
[KNOWLEDGE_PLAN.md](KNOWLEDGE_PLAN.md). Build it in its order (section 8):

1. ~~Site profile and sync with admin-approved diffs~~ (done, "7." above; leftovers listed there).
2. ~~Knowledge store in Postgres, draft/publish, code-level import~~ (done, "11." above).
3. ~~Admin API under `/api/v1/sites/{site_id}/knowledge/...`~~ (done with step 2).
4. ~~Site functions~~ (done, "12." above: backend-ot's functions labelled `ai_assistant`,
   approved per site; no gateway library, no bindings).
5. web-plusdas Knowledge pages.
6. Persistent conversations, per-site grants.
7. Growth loop: gap log, conversation to note, verified answers.
8. Answer cost: cost logging, direct lookups, answer cache, model per run, budgets.

Also open: run `make test-llm` (the real-Claude test) and keep it passing; cut token use
(`get_device_status` returns about 50 points per device; long point names).

## Known issues and gaps
- **Mode flags look like alarms.** backend-ot's powerflow seed marks every bitfield as an ALARM
  point, so `DERMode` shows up as an "active alarm". Claude explains it correctly, but it is
  noise. This is logged in `TODO_MONOREPO_TASKS.md` and is a backend-ot change.
- **backend-ot gaps the client works around:**
  - point descriptions are only the device profile's one-liner (`profile_point_description`,
    copied since 2026-11-07); the engineer guides cover meaning
  - no stored data quality and no poll history (a device's last reading time stands in for comms
    health)
  - no min/max/avg endpoint (history is summarized on the client)
- **No engineer knowledge yet:** since item 8 there are no fictional guides at runtime, so
  `explain_point` / `lookup_fault` find nothing until the Postgres knowledge store (plan step 2).
- **Conversations are lost on restart,** and concurrent requests to the same conversation are
  not serialized.
- **Not built yet:**
  - SSO / an external identity provider (OIDC); local accounts exist (step 6), and only
    `api/dependencies.py::get_request_context` would change. No login rate limiting yet.
  - OpenTelemetry (`utils/telemetry.py` is a no-op hook)
  - tools that perform actions; any such tool needs explicit human approval

## Useful commands

```sh
make -C services/intelli-gateway lint typecheck test       # test doubles, scripted Claude, no network
make -C services/intelli-gateway test-integration          # Postgres tests (Docker, throwaway DB)
make -C services/intelli-gateway test-llm                  # real Claude API (costs tokens)
make -C services/intelli-gateway contract                  # after any API change
make check-boundaries                                      # repo-wide boundary check
# ask a question (dev stack running, ANTHROPIC_API_KEY in the service .env)
curl -X POST localhost:8030/api/v1/sites/1/ask -H 'Content-Type: application/json' \
  -d '{"question": "Why is INV2 producing less than INV1?"}'
```
