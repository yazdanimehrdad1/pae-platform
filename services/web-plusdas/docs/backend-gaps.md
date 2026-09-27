# What the UI needs from backend-ot that it doesn't have yet

Status as of 2026-09-25. Everything the UI shows that isn't in backend-ot's contract
(`contracts/openapi/backend-ot.openapi.json`) is listed here, with what backend-ot would need
to provide. **Decision (user, 2026-09-25):** the frontend keeps these mocks. Closing a gap is
backend-ot work first (its `add-endpoint` skill, then `make contract`), then the frontend
(`add-api-call` skill). Don't write client functions or types for a route before it exists.

## Pages running on mock or placeholder data

| Page / feature | Today | What backend-ot would need |
|---|---|---|
| **Login / auth** (`src/mocks/auth.ts`, used by `src/shared/contexts/auth.tsx`) | Accepts any email and password and keeps the "user" in localStorage. backend-ot has no auth at all: every route is open. | A design decision first: auth at the platform reverse proxy (e.g. Keycloak/OIDC in front of both) or in backend-ot. Then a session/user endpoint (e.g. `GET /api/me`) for the UI to read. |
| **System alarms** (`src/mocks/alarms/`, used through `features/alarms/data/source.ts`) | The whole page: 8 fake devices with Modbus points, value signals over 7 days, alarm rules and their notification switches (in memory, lost on reload). Alarms are derived by the frontend rule engine. | backend-ot has only a live reachability snapshot (`GET /api/healthz/site/{site_id}`). It needs: alarm rules stored and evaluated **server-side** (threshold with delay + deadband, comms stale), each with notification channels (`notify: {mobile, email}`) and a `name` that is an identifier (`^[A-Za-z_][A-Za-z0-9_]*$`, max 150, unique ignoring case, validated server-side); an alarm event store with raise/clear times; routes for a snapshot, an events query and rules CRUD; a push channel (SSE/WebSocket) for changes; and mobile push + email sending for rules with those channels on (recipients still to be designed). The expected call shapes are in `src/features/alarms/README.md`. Trends can use the existing readings timeseries. |
| **Single-line diagram** (`src/mocks/sld/`, used by `features/sld/lib/sldDataMerger.ts`) | Loads static JSON from `src/mocks/sld/sld-layout.json` and `sld-data.json`. | The layout (buses, devices, connections per site) as stored data, and live values per SLD device, e.g. `GET /api/sites/{site_id}/sld/layout` and `.../sld/data`. The field shapes are the ones in `features/sld/types.ts`. |
| **Notes** (`features/notes/`, `lib/notesStorage.ts`) | Stored in the browser's localStorage per user. They are lost with the browser and not shared. | Notes storage (CRUD per site/device/user), if notes should be shared or kept. |
| **Narrative, Reports, AI Task Builder, Settings (teams), Users** | Static placeholder pages (no data calls). Reports and Task Builder show fake lists from `src/mocks/reports.ts` and `src/mocks/tasks.ts`. | Product decisions, then APIs. Out of scope until those exist. |

The pages on real data are Sites, Site Devices, Device details, Historian, and Live Data.

## Fields the UI defaults because backend-ot doesn't send them

- **Site `type` and `status`** (`src/api/sites.ts`, `toSite`): `SiteResponse` has neither, so
  every site shows as type "facility" and status "online".
- **Device `status`, `commStatus`, `firmware`, serial number** (`src/api/devices.ts`,
  `toDevice`): status is always "online", commStatus is derived from `poll_enabled`, firmware
  is empty, and the serial number is the device id. Real values need backend-ot to expose the
  last poll outcome (time, success, error) per device, and device metadata.

## Contract accuracy (backend-ot's OpenAPI vs. what it actually does)

Found while switching the UI to generated types. Each one makes the UI stricter or looser than
needed. None is a runtime bug today.
- **Request fields with defaults are published as required.** Examples:
  `LiveStreamRawRegistersRegisterConfig.data_type` (really defaults to `int16`), and
  `LiveStreamRawRegistersParams.port`, `kind`, `interval`... The UI now always sends them. The
  contract should mark them optional (FastAPI separate input/output schemas, or `Field(default=...)`
  surfacing as not required).
- **Response enum fields are plain strings.** `DeviceWithPoints.type/protocol/modbus_address_mode`,
  `DevicePointResponse.category/poll_kind`, `LiveStreamSessionInfo.modbus_address_mode` are
  `str` in responses but `Literal[...]` in requests, so the UI casts them back
  (`DeviceFormDialog.fromDevice`, `useModbusSessions`). Using the same `Literal` types in the
  response models would remove the casts.
- **Device `type` accepts any casing on input** (`_normalize_device_type`), but the contract
  publishes only the uppercase enum. That's fine: the UI sends uppercase.
- **SSE payloads aren't described.** The live-stream events (`connected`, `poll`, `done`) are
  hand-written in `src/api/types/modbusStream.ts`. OpenAPI 3.1 can't model an event
  stream well, so a small JSON Schema for the event data published in `contracts/` would let
  the UI generate them too.
