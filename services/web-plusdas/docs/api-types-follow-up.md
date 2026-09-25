# Follow-up: generate the API types from backend-ot's contract

Status: **not done.** The frontend's API types are hand-written. This note inventories them and
proposes how to generate them from `contracts/openapi/backend-ot.openapi.json` without breaking
the extractability invariant (see `CLAUDE.md`). Adopting it adds a devDependency, so it needs
the user's OK.

## What exists today (all hand-written)

| File | Types |
|---|---|
| `src/shared/types/api.ts` | ApiResponse, PaginatedResponse, ApiError, TimeSeriesRequest, TimeSeriesPoint, TimeSeriesResponse, TimeRange, DevicePointReadingsRequest, BackendPointReadings, HealthStateResponse, SiteListResponse |
| `src/shared/types/device.ts` | Device, RegisterRange, DeviceScanRanges, DeviceRecord, DeviceCreateRequest, DeviceUpdateRequest, DeviceDeleteResponse |
| `src/shared/types/device-point.ts` | DevicePoint, DevicePointCreateRequest, DevicePointUpdateRequest |
| `src/shared/types/site.ts` | Site, SiteLocation, SiteCoordinates, SiteRecord, SiteCreateRequest, SiteUpdateRequest, SiteDeleteResponse |
| `src/shared/types/historian.ts` | AssetNode, HistorianMetadata |
| `src/shared/types/modbusLiveStream.ts` | ModbusRegisterKind, ModbusAddressMode, ModbusByteOrder, ModbusWordOrder, ModbusRegisterConfig, ModbusLiveStreamRequest, the SSE event types, ModbusSessionSummary, ... |
| `src/api/sites.ts` (inline) | BackendSite |
| `src/api/devices.ts` (inline) | PointResponse, ScanRange, DeviceResponse, DevicePointsEntry, PingResult |
| `src/features/sld/types.ts` | SLD layout/data types (the SLD endpoints are not called yet; the page loads mock JSON) |

Endpoints called (all under `/api`): `sites` (list/get/create/update/delete/restore),
`devices/site/{siteId}/devices[/{deviceId}]` (+ restore), `healthz/site/{siteId}/device/{deviceId}`,
`device-points/site/{siteId}/device/{deviceId}` (+ bulk, scan-ranges, restore),
`device-point-readings/timeseries/...`, and `modbus-live-stream-raw-registers/{stream,sessions}` (SSE).
The client modules also define `sites/{id}/health`, `sites/{id}/historian/*` and `sites/{id}/sld/*`,
which no page calls. Check them against the spec: they may not exist in backend-ot.

## Recommendation: openapi-typescript, output committed here

- **Tool: [openapi-typescript](https://openapi-ts.dev/)** (devDependency). It emits TypeScript
  types only, with no runtime code, from an OpenAPI 3.1 document, which is what backend-ot publishes.
  It fits the existing thin `fetch` client. `openapi-fetch` (a typed fetch wrapper from the same
  project) could replace `src/api/client.ts` later, as a separate decision.
- **How it fits the contracts/ + export-script pattern:** backend-ot runs `make contract`, which
  runs `scripts/export_openapi.py`, which writes `contracts/openapi/backend-ot.openapi.json`, which
  is committed. The consumer side mirrors that:
  - `make -C services/web-plusdas api-types` reads `$(CONTRACTS_DIR)/openapi/backend-ot.openapi.json`
    with `CONTRACTS_DIR ?= ../../contracts` defined once in the Makefile. It writes
    `src/api/generated/backend-ot.ts`, and that file is **committed**.
  - Committing it keeps the Docker build context `services/web-plusdas` only. The image never
    needs `contracts/`.
  - Drift check: `make test` regenerates and runs `git diff --exit-code src/api/generated`, like
    backend-ot's `tests/unit/test_contract.py`. The root `contracts` skill adds "regenerate web's
    types" to the consumer step.
- **One alias, one place:** a tsconfig `paths` + vite `resolve.alias` entry
  `@contracts/backend-ot` points at the generated file, and the code imports only from there.
  **On extraction**, contracts/ becomes a published package. Change `CONTRACTS_DIR` (or point
  `api-types` at the package), and nothing in `src/` changes.
- `check_boundaries.py` already allows `../` paths from this service into `contracts/` (Makefile,
  tsconfig) and rejects any path into another service.

## Other follow-ups found during the import

- A unit-test runner (vitest; new devDependency) so `make test` tests something.
- Make `make typecheck` blocking: fix the 7 pre-existing tsc errors, then consider `strict: true`.
- Remove the unused `lovable-tagger` devDependency and the Lovable meta tags in `index.html`.
  Rename `package.json` `name` (`vite_react_shadcn_ts`).
- Delete the inert tracked `.env.development` / `.env.production`.
- Wire the mock-only pages to backend-ot: HealthPage (`useMockHealth`), SLD (`sld/test/*.json`),
  and real auth (Keycloak/OAuth).
- Run nginx as non-root (e.g. `nginxinc/nginx-unprivileged`, listening on 8080).
- A web skill (proposed: `add-api-call`, which adds a backend-ot call end to end: client fn, types,
  React Query hook, and a same-origin/no-trailing-slash check against the contract). The user decides.
