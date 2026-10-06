# mobile-plusdas

The PAE mobile app (Expo SDK 57 / React Native, iOS + Android, expo-router, TypeScript strict).
**Bare-bones on purpose:** it lists backend-ot's sites, and that's all. The Alarms, Reports and
Assistant tabs say "coming soon". Alarms, push notifications, reports and the AI assistant come
later, backend first (see `TODO_MONOREPO_TASKS.md`). It is NOT a historian.

**Owns:** the app's screens and its on-device settings (the server URL).
**Does not own:** any data or API; backend-ot owns sites.

## Boundaries
- Depends only on `contracts/` and its own files. `scripts/api-types.mjs` is the ONE place that
  points at `../../contracts`. The generated types are committed (`src/api/generated/`).
- Not containerized and not in `deploy/compose/`. `up/down/down-all/logs` are no-ops so the
  root loops pass through.
- No root package.json, no workspace. npm only, Node 24.
- Unlike web-plusdas, the app calls an **absolute** server URL (a phone has no same origin).
  The URL is chosen at runtime in Settings and stored on the device. In development the default
  is derived from the Metro host the app was loaded from (`serverUrlFromDevHost`: same PC,
  backend-ot's port). Otherwise it is the build's `DEFAULT_SERVER_URL`. A URL saved in Settings
  wins; "Use detected" goes back.

## Try it on a phone (from the repo root)
```
make mobile-dev     # stack + a site if needed, phone checks, Metro QR -> scan in Expo Go
```
The helper is `scripts/mobile/dev.py` (HTTP only). Settings shows whether the server answers.

## Commands (`make -C services/mobile-plusdas <target>`)
- `install`: run `npm ci`.
- `lint`, `lint-fix`, `format` (prettier), `typecheck` (`tsc --noEmit`).
- `test`: checks that `api-types` matches the contract, then runs jest (jest-expo plus
  @testing-library/react-native). No device or emulator needed.
- `api-types`: regenerates `src/api/generated/backend-ot.ts` after backend-ot's contract changes.
- `build`: runs `expo export` for Android and iOS into `dist/`. This is a bundling check, not a store build.
- `run`: starts Metro on port 8081. Open it in Expo Go on the same Wi-Fi.
- `eas-build-dev` / `eas-build-preview`: EAS cloud builds (EAS project in `app.config.ts`, needs `eas login`).

## Layout (imports point one way: `app/` → `src/features` → `src/api` / `src/shared`)
```
app/                       expo-router routes only, thin (each renders a feature screen)
  _layout.tsx              providers, server URL load, focusManager
  (tabs)/                  Sites | Alarms, Reports, Assistant ("coming soon") | Settings
src/api/                   client.ts (apiFetch, ApiError), backendOt.ts (sites, health),
                           types.ts (aliases of generated schemas), queryKeys.ts
src/features/sites/        Sites tab: a plain, read-only list sorted by name (useSites)
src/features/settings/     server URL, detected URL, connection status
src/shared/                theme tokens, persistedValue (AsyncStorage), usePullToRefresh, ui
tests/                     mirrors src/, imports via @/
```
ESLint stops `src/api` and `src/shared` from importing `src/features`.

## UI rules
- Colors are web-plusdas's palette (its `src/index.css` variables, as hex in `src/shared/theme/tokens.ts`),
  dark by default like web-plusdas. Copied, not imported: update both when the web theme changes.
- The Sites tab shows no alarm state: no colors, counts or severity. Tapping a site does nothing yet.
- Pull-to-refresh spinners follow only the user's pull (`usePullToRefresh`), never background
  refetches, or they flash and look like the screen reloading.
- When alarms come back, follow web-plusdas's alarms rules (ISA-101 / ISA-18.2): grey is
  normal, green never means OK, severity is always color + icon + word.

## Contracts (rules: `contracts/README.md`, procedure: root `contracts` skill)
- **Consumes** `contracts/openapi/backend-ot.openapi.json` (`/api/sites`, `/api/healthz`).
  `make test` fails while the generated types are stale.

## Gotchas
- **TypeScript is pinned to 5.9**, not SDK 57's 6.0, because openapi-typescript 7 peers on TS 5.
  `expo.install.exclude` keeps `expo install --check` quiet about it.
- **react-dom is a dev dependency** only to satisfy a test peer at react 19.2.3. Don't let npm
  float it to a version that doesn't match `react`.
- Jest maps `lucide-react-native` to its CJS build (its ESM build is `.mjs`, which jest-expo
  doesn't transform). AsyncStorage uses its official mock (`tests/setup.ts`).
- The phone must reach backend-ot on the dev machine's LAN IP and port 8000, not `localhost`.
  If it can't, it's the Windows firewall or a 'Public' Wi-Fi profile (`make mobile-dev` prints the
  fix). Release builds (`preview`) need HTTPS, or a cleartext exception, to reach an http:// server.
- There is no auth yet (backend-ot has none). Don't point a build at a server reachable from the
  internet until auth and a gateway exist.
- Native `ios/` and `android/` are generated (CNG) and gitignored. Change native config through
  `app.config.ts` and plugins, not by editing them.
