// Each build names its JavaScript chunks by content hash, and a new deploy serves only the new ones.
// A tab opened before the deploy still runs the old app, so opening a lazy-loaded page asks for an
// old chunk that is gone (404). Reloading fetches the current index.html (served no-cache) and the
// current chunks. A short guard stops a reload loop when the server is really unreachable.

const RELOADED_AT_KEY = "pae.staleBuildReloadedAt";
const RELOAD_GUARD_MS = 10_000;

/** A lazy import that failed because its chunk couldn't be fetched (Chrome, Firefox, Safari). */
export function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? "");
  return /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed/i.test(message);
}

/** Reload the page to pick up the current build, unless it was just tried. Returns whether it reloads. */
export function reloadForNewBuild(now: number = Date.now(), reload: () => void = () => window.location.reload()): boolean {
  let lastReload = 0;
  try {
    lastReload = Number(window.sessionStorage.getItem(RELOADED_AT_KEY) ?? 0);
  } catch {
    // Storage blocked: reload anyway; worst case the user sees the error after one reload.
  }
  if (now - lastReload < RELOAD_GUARD_MS) return false;
  try {
    window.sessionStorage.setItem(RELOADED_AT_KEY, String(now));
  } catch {
    // see above
  }
  reload();
  return true;
}
