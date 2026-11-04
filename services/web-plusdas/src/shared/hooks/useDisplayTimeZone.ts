import { useCallback } from "react";
import { PREFERENCE_KEYS, usePreference } from "./usePreference";

// Pages show a site's times in the site's time zone (the site's day is the same for everyone). The
// user can switch to their own zone; the choice is one of the user's preferences (it follows them
// to any browser) and applies to every page (Historian, System alarms, Reports) at once.

export type TimeDisplay = "site" | "browser";

export const BROWSER_TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

const isTimeDisplay = (value: unknown): value is TimeDisplay => value === "site" || value === "browser";

/** The zone to show `siteTimeZone`'s times in: the site's, or the browser's if the user chose
 * "my time" (or the site's zone isn't known yet). */
export function useDisplayTimeZone(siteTimeZone: string | null | undefined) {
  const [display, saveDisplay] = usePreference<TimeDisplay>(PREFERENCE_KEYS.timeDisplay, "site", isTimeDisplay);
  const setDisplay = useCallback((next: TimeDisplay) => saveDisplay(next), [saveDisplay]);
  const timeZone = display === "browser" || !siteTimeZone ? BROWSER_TIME_ZONE : siteTimeZone;
  return { display, setDisplay, timeZone, siteTimeZone: siteTimeZone ?? null };
}
