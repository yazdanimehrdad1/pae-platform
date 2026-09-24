---
name: add-endpoint
description: Add or change a backend-ot HTTP endpoint (route, query/path parameter, request or response model, status code) and publish it in the OpenAPI contract. Use for "add an endpoint", "expose X on the API", "add a field to the devices response", "new route under /api/...", "change what GET /api/sites returns", or any edit under src/api/routers/.
---

# Add or change a backend-ot endpoint

Every route change is also a **contract change**: `contracts/openapi/backend-ot.openapi.json`
is generated from the app, and `make test` fails until it is regenerated. The conventions
below are this service's CLAUDE.md ("Typing", "Integration tests are required", "Linting");
this skill is the order to apply them in.

## Layers (follow an existing router, e.g. `src/api/routers/sites.py`)

- **Router** `src/api/routers/<resource>.py`: `router = APIRouter(prefix="/<resource>", ...)`.
  Thin: parse input, call the controller, map errors. Every route declares `response_model`,
  a `summary`, and the explicit `status_code` when it isn't 200. Errors use the existing
  pattern: catch `AppError` → `HTTPException(e.http_status_code, detail={"error": ..., "message": ...})
  from e`; catch-all → 500 with `from e`; a lookup miss → 404.
- **Controller** `src/api/controllers/<resource>.py`: calls `db/` or `helpers/`. Business rules
  raise the typed errors in `src/utils/exceptions.py` (`NotFoundError`, `ConflictError`,
  `ValidationError`), never bare `Exception`.
- **Models**: reuse `src/schemas/api_models/` first; new request models go in `requests.py`,
  response models in `responses.py`, both re-exported from `schemas/api_models/__init__.py`.
  No `dict`/`Any` for structured data.
- **A new router module** must be mounted in `create_app()` in `src/app.py`
  (`app.include_router(<module>.router, prefix="/api", tags=[...])`).
- A schema change (new table/column) → the `add-migration` skill first.

## Procedure

1. Write the models, then the DB/helper and controller code, then the route.
2. Integration tests in `tests/integration/api/routers/test_<router>.py` (mirror `src/`;
   `__init__.py` in every folder): arrange through `integration.factories`, use the `client`
   fixture, parse bodies with `Model.model_validate(...)`, cover the happy path **and** the
   error paths (404/409/400/422). Unit tests under `tests/unit/` for any non-trivial logic.
3. Regenerate the contract: `make -C services/backend-ot contract`.
4. Review `git diff -- contracts/openapi/` and classify it with the root `contracts` skill
   (additive vs breaking; a breaking change needs the user's OK and a version bump).

## Done when

- `make -C services/backend-ot lint` passes.
- `make -C services/backend-ot test` passes — includes `tests/unit/test_contract.py`, which
  fails with "contract is stale" if step 3 was skipped.
- `make -C services/backend-ot test-integration` passes.
- `make contracts-check` at the repo root prints `contracts/ is current` (stage the spec first).
- Optional live check: `make up` at the root, then call the route on
  `http://localhost:8000/api/...` (see the `run-platform` skill).
