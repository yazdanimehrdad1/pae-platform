import { useCallback, useSyncExternalStore } from "react";

// Pages show a site's times in the site's time zone (the site's day is the same for everyone). The
// user can switch to their own zone; the choice is remembered in this browser and applies to every
// page (Historian, System alarms, Reports) at once.

export type TimeDisplay = "site" | "browser";

export const BROWSER_TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

const STORAGE_KEY = "pae.timeDisplay";
const listeners = new Set<() => void>();

function readDisplay(): TimeDisplay {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "browser" ? "browser" : "site";
  } catch {
    return "site";
  }
}

function writeDisplay(display: TimeDisplay): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, display);
  } catch {
    // Storage blocked (private mode): the choice lasts until reload.
  }
  current = display;
  listeners.forEach(listener => listener());
}

let current: TimeDisplay = typeof window === "undefined" ? "site" : readDisplay();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) {
      current = readDisplay();
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** The zone to show `siteTimeZone`'s times in: the site's, or the browser's if the user chose
 * "my time" (or the site's zone isn't known yet). */
export function useDisplayTimeZone(siteTimeZone: string | null | undefined) {
  const display = useSyncExternalStore(subscribe, () => current, () => "site" as TimeDisplay);
  const setDisplay = useCallback((next: TimeDisplay) => writeDisplay(next), []);
  const timeZone = display === "browser" || !siteTimeZone ? BROWSER_TIME_ZONE : siteTimeZone;
  return { display, setDisplay, timeZone, siteTimeZone: siteTimeZone ?? null };
}
