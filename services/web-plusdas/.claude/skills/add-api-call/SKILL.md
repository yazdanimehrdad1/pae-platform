---
name: add-api-call
description: Add or change a web-plusdas call to backend-ot, from the API client to the page, with types from the contract. Use for "call endpoint X from the UI", "show Y on the page", "wire this page to the backend", "add a field from the API to the table", "replace this mock with real data", or any edit under services/web-plusdas/src/api/.
---

# Add or change a backend-ot call in web-plusdas

The UI talks to backend-ot only through `src/api/`, on the same origin (`/api`), with types
generated from backend-ot's contract. The rules are in this service's CLAUDE.md ("Runtime
config and same-origin", "Contracts"). This skill is the order to apply them in.

## 1. Check the route exists in the contract, first
- Find it in `contracts/openapi/backend-ot.openapi.json` (method, path, query parameters,
  request body, response schema). Or read the generated `paths` in
  `src/api/generated/backend-ot.ts`.
- **It isn't there?** The UI can't call it. backend-ot must add it first (its `add-endpoint`
  skill, then `make -C services/backend-ot contract`), which is a separate change in the
  provider. Don't write a client function for a route that doesn't exist, and don't invent a
  response type. List the gap in `docs/backend-gaps.md` if it isn't done now.
- If the contract changed since the last `make api-types`, run it: `make -C services/web-plusdas api-types`.

## 2. Types: from the contract, never hand-written
- Wire types live in `src/shared/types/<resource>.ts` as aliases:
  `export type X = components['schemas']['XResponse'];` (import from `@contracts/backend-ot`,
  never a relative path into `src/api/generated/`). Enum-like values (device types, data types,
  kinds) come from the schema too, e.g. `Schemas['DeviceCreateRequest']['type']`.
- A UI option list for an enum is a `Record<ThatEnum, Label>`, so a contract change fails the
  typecheck (see `DEVICE_TYPE_LABELS` in `src/features/sites/DeviceFormDialog.tsx`).
- UI view models (what a page renders, e.g. `Site`, `Device`) stay hand-written, next to their
  mapping function (`toSite`, `toDevice` in `src/api/`).
- Server-sent-event payloads aren't in the OpenAPI contract, so those stay hand-written in
  `src/shared/types/`, with a comment saying so.

## 3. The client function (`src/api/<resource>.ts`)
- Use `client.get/post/put/delete/action` or `request` from `./client`. The base URL is already
  `/api` from runtime config: write `'/sites'`, never an absolute URL and **never a trailing
  slash** (backend-ot 307s it).
- Query parameters go through `URLSearchParams`. An array parameter (`items: integer` in the
  contract) is **repeated** (`params.append('ids', ...)` for each), never comma-joined, unless the
  contract declares a comma-separated string (like the readings `point_ids`).
- Type the call with the contract type: `client.get<SiteRecord[]>('/sites')`. Map to a view
  model in the same module if the page needs one.
- A streaming (SSE) route uses `streamSse` from `./sse` and needs its own nginx location with
  buffering off in `docker/nginx/default.conf.template`.
- Export it from `src/api/index.ts` if pages import from `@/api`.

## 4. Use it in the page
- Through React Query (`useQuery` for reads, `useMutation` + `invalidateQueries` for writes),
  like the existing pages (`src/features/sites/`, `src/features/devices/`). Show errors with
  `getErrorMessage(error)` (it reads FastAPI's `detail`).

## 5. Tests
- `src/api/<resource>.test.ts`: stub `fetch` with `vi.stubGlobal` and assert the URL (path,
  repeated params), method, body, and the mapping. See `src/api/devices.test.ts`.
- For a form or a component with logic, add a component test with Testing Library
  (`// @vitest-environment jsdom`, see `src/features/sites/DeviceFormDialog.test.tsx`).

## Done when
- `make -C services/web-plusdas lint typecheck test` passes. `test` includes the
  API-types drift check.
- With the dev stack up (`make up` at the root), the page works on http://localhost:5173, and
  the Network tab shows the call going to `/api/...` on that origin. `make -C services/web-plusdas test-integration` passes.
- `make check-boundaries` passes (no path outside this service except into `contracts/`).
