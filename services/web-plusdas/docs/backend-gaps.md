# What the UI needs from backend-ot that it doesn't have yet

Status as of 2026-09-25. Everything the UI shows that isn't in backend-ot's contract
(`contracts/openapi/backend-ot.openapi.json`) is listed here, with what backend-ot would need
to provide. **Decision (user, 2026-09-25):** the frontend keeps these mocks. Closing a gap is
backend-ot work first (its `add-endpoint` skill, then `make contract`), then the frontend
(`add-api-call` skill). Don't write client functions or types for a route before it exists.

## Pages running on mock or placeholder data

| Page / feature | Today | What backend-ot would need |
|---|---|---|
| **Login / auth** (`src/shared/contexts/auth.tsx`, `features/auth/LoginPage.tsx`) | Accepts any email and password and keeps the "user" in localStorage. backend-ot has no auth at all: every route is open. | A design decision first: auth at the platform reverse proxy (e.g. Keycloak/OIDC in front of both) or in backend-ot. Then a session/user endpoint (e.g. `GET /api/me`) for the UI to read. |
| **Health timeline** (`features/health/HealthPage.tsx`, `hooks/useMockHealth.ts`) | 48 h of random three-state health (normal/warning/lost) for 8 hard-coded fake devices. | backend-ot has only a live snapshot: `GET /api/healthz/site/{site_id}` gives reachable/unreachable per device, right now. A timeline needs health *history*: ping or poll results stored over time, e.g. `GET /api/healthz/site/{site_id}/history?time_range=1D` giving per-device state changes with timestamps. A "warning" state needs a definition (poll errors? latency?). |
| **Single-line diagram** (`features/sld/`, `lib/sldDataMerger.ts`) | Loads static JSON from `features/sld/test/sld-layout.json` and `sld-data.json`. | The layout (buses, devices, connections per site) as stored data, and live values per SLD device, e.g. `GET /api/sites/{site_id}/sld/layout` and `.../sld/data`. The field shapes are the ones in `features/sld/types.ts`. |
| **Notes** (`features/notes/`, `src/lib/notesStorage.ts`) | Stored in the browser's localStorage per user. They are lost with the browser and not shared. | Notes storage (CRUD per site/device/user), if notes should be shared or kept. |
| **Narrative, Reports, AI Task Builder, Settings (teams), Users** | Static placeholder pages (no data calls). | Product decisions, then APIs. Out of scope until those exist. |

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
  hand-written in `src/shared/types/modbusLiveStream.ts`. OpenAPI 3.1 can't model an event
  stream well, so a small JSON Schema for the event data published in `contracts/` would let
  the UI generate them too.

## Unused mock files (kept on purpose, removable any time)

`Tests/devices.ts`, `Tests/sites.ts`, `src/shared/test/historian.ts` and
`features/historian/hooks/useMockSeries.ts` are not imported by any page.
