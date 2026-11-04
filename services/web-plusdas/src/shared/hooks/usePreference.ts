import { useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { meApi } from "@/api/me";
import type { Preference } from "@/api/types/me";

// The logged-in user's preferences, kept by intelli-gateway so they follow the user to any
// browser or device. All of them load in one request, shared by every page. A change shows at
// once and is saved in the background; saves of one key go out in order, so the last one wins.

export const PREFERENCES_QUERY_KEY = ["me", "preferences"] as const;

// The keys in use, in one place (intelli-gateway accepts any lower-case key).
export const PREFERENCE_KEYS = {
  timeDisplay: "time-display",
  lastSite: "site-devices.last-site",
  discreteMode: "historian.discrete-mode",
  liveDataConfigs: "live-data.configs",
  liveDataSessions: "live-data.sessions",
} as const;

type PreferenceMap = Record<string, unknown>;

const pendingSaves = new Map<string, Promise<unknown>>();
// Values set but not saved yet: laid over what a load returns, so a choice made while the
// preferences are still loading (or reloading) is never overwritten by the older stored value.
const unsavedValues = new Map<string, unknown>();

async function loadPreferences(): Promise<Preference[]> {
  const stored = await meApi.listPreferences();
  if (unsavedValues.size === 0 || !Array.isArray(stored)) return stored;
  const merged = stored.filter(preference => !unsavedValues.has(preference.key));
  unsavedValues.forEach((value, key) => merged.push({ key, value: value as Preference["value"], updated_at: new Date().toISOString() }));
  return merged;
}

function toMap(preferences: Preference[] | unknown): PreferenceMap {
  if (!Array.isArray(preferences)) return {};
  return Object.fromEntries(preferences.map((preference: Preference) => [preference.key, preference.value]));
}

/** Every preference by key; empty until loaded (and when loading fails: the defaults then apply). */
export function usePreferences() {
  return useQuery({
    queryKey: PREFERENCES_QUERY_KEY,
    queryFn: loadPreferences,
    select: toMap,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

/** One preference: its stored value when `isValid` accepts it, else `fallback`; and a setter. */
export function usePreference<T>(
  key: string,
  fallback: T,
  isValid: (value: unknown) => value is T,
): [T, (next: T) => void, { isLoaded: boolean }] {
  const queryClient = useQueryClient();
  const { data, isSuccess, isError } = usePreferences();
  const stored = data?.[key];
  const value = useMemo(() => (isValid(stored) ? stored : fallback), [stored, fallback, isValid]);

  const setValue = useCallback((next: T) => {
    unsavedValues.set(key, next);
    queryClient.setQueryData<Preference[]>(PREFERENCES_QUERY_KEY, (previous) => {
      const others = (Array.isArray(previous) ? previous : []).filter(preference => preference.key !== key);
      return [...others, { key, value: next as Preference["value"], updated_at: new Date().toISOString() }];
    });
    const save = (pendingSaves.get(key) ?? Promise.resolve())
      .catch(() => undefined)
      .then(() => meApi.putPreference(key, next))
      .then(() => { if (unsavedValues.get(key) === next) unsavedValues.delete(key); })
      .catch((error) => {
        if (unsavedValues.get(key) === next) unsavedValues.delete(key);
        console.warn(`Could not save the preference ${key}`, error);
        void queryClient.invalidateQueries({ queryKey: PREFERENCES_QUERY_KEY });
      });
    pendingSaves.set(key, save);
  }, [queryClient, key]);

  return [value, setValue, { isLoaded: isSuccess || isError }];
}
