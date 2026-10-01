# Mocks

Everything the UI fakes lives in this folder, so `grep -r "@/mocks" src` lists exactly what is
still not real. Each mock waits on a backend-ot API that doesn't exist yet
(`docs/backend-gaps.md`). Deleting a file here breaks the build only where real data must replace it.

| File | Used by | Stands in for |
|---|---|---|
| `auth.ts` | `shared/contexts/auth.tsx` | Login (accepts any email/password) |
| `sld/` | `features/sld/` (`lib/sldDataMerger`, `SLDPage`) | SLD layout + live data per site, diagram list |
| `reports.ts` | `features/reports/ReportsPage` | Report catalogue and generated reports |
| `tasks.ts` | `features/task-builder/TaskBuilderPage` | AI tasks |

## Rules
- Import mocks only from features (preferably one hook or lib function per feature, the swap
  point) and from `shared/contexts/auth.tsx`. Never from `src/api/` or `src/components/`: ESLint
  enforces that.
- Mocks use the feature's or the API's types, so a mock that drifts from the real shape fails
  `make typecheck`.
- Replacing a mock with real data: backend-ot adds the route first, then the `add-api-call`
  skill; delete the mock and its row here in the same change.
