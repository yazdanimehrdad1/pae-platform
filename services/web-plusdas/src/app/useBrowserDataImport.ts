import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { meApi } from "@/api/me";
import { PREFERENCE_KEYS } from "@/shared/hooks/usePreference";
import { parseLegacyTrends, toDefinition } from "@/features/historian/lib/savedTrends";
import { isDiscreteModeId } from "@/features/historian/components/discrete/discreteModes";

// Before accounts, each browser kept the user's trends, notes and settings in localStorage. On
// the first login in such a browser, this copies them to the logged-in user (intelli-gateway),
// then removes them: they go to the first person who logs in there, once.
// - preferences: only the ones the user hasn't set yet
// - trends and notes: only if the user has none yet (so a retry never duplicates them)
// It runs before any page loads. A failure leaves the old data in place for the next login.

const LEGACY_PREFIXES = {
  trends: "historian_trends_",
  discreteMode: "historian_discrete_mode_",
  liveDataConfigs: "modbus_config_cache_",
  liveDataSessions: "modbus_session_cache_",
} as const;
const LEGACY_KEYS = {
  notes: "user_notes",
  lastSite: "site_devices_last_site",
  timeDisplay: "pae.timeDisplay",
  mockUser: "user",
} as const;
const MAX_IMPORTED_TRENDS = 4; // the Historian's own limit

function storageKeys(): string[] {
  try {
    return Object.keys(window.localStorage);
  } catch {
    return []; // storage blocked: nothing to import
  }
}

function legacyKeys(): string[] {
  const exact = new Set<string>(Object.values(LEGACY_KEYS));
  const prefixes = Object.values(LEGACY_PREFIXES);
  return storageKeys().filter(key => exact.has(key) || prefixes.some(prefix => key.startsWith(prefix)));
}

function read(key: string | undefined): string | null {
  if (!key) return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function readJson(key: string | undefined): unknown {
  const stored = read(key);
  if (stored === null) return undefined;
  try {
    return JSON.parse(stored);
  } catch {
    return undefined;
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

interface LegacyNote { content: string; createdAt?: string; updatedAt?: string }

function legacyNotes(): LegacyNote[] {
  const stored = readJson(LEGACY_KEYS.notes);
  if (!Array.isArray(stored)) return [];
  return stored.filter((note): note is LegacyNote =>
    isRecord(note) && typeof note.content === "string" && note.content.trim() !== "");
}

const validDate = (value: string | undefined) =>
  value && !Number.isNaN(Date.parse(value)) ? new Date(value).toISOString() : undefined;

/** Copies the browser's old data to the logged-in user, then removes it. */
export async function importBrowserData(): Promise<void> {
  const keys = legacyKeys();
  if (keys.length === 0) return;
  const withPrefix = (prefix: string) => keys.find(key => key.startsWith(prefix));

  const stored = new Set((await meApi.listPreferences()).map(preference => preference.key));
  const preferences: [string, unknown, boolean][] = [
    [PREFERENCE_KEYS.timeDisplay, read(LEGACY_KEYS.timeDisplay), ["site", "browser"].includes(read(LEGACY_KEYS.timeDisplay) ?? "")],
    [PREFERENCE_KEYS.lastSite, read(LEGACY_KEYS.lastSite), Boolean(read(LEGACY_KEYS.lastSite))],
    [PREFERENCE_KEYS.discreteMode, read(withPrefix(LEGACY_PREFIXES.discreteMode)), isDiscreteModeId(read(withPrefix(LEGACY_PREFIXES.discreteMode)))],
    [PREFERENCE_KEYS.liveDataConfigs, readJson(withPrefix(LEGACY_PREFIXES.liveDataConfigs)), isRecord(readJson(withPrefix(LEGACY_PREFIXES.liveDataConfigs)))],
    [PREFERENCE_KEYS.liveDataSessions, readJson(withPrefix(LEGACY_PREFIXES.liveDataSessions)), isRecord(readJson(withPrefix(LEGACY_PREFIXES.liveDataSessions)))],
  ];
  for (const [key, value, isValid] of preferences) {
    if (isValid && !stored.has(key)) await meApi.putPreference(key, value);
  }

  const trends = parseLegacyTrends(read(withPrefix(LEGACY_PREFIXES.trends))).slice(0, MAX_IMPORTED_TRENDS);
  if (trends.length > 0 && (await meApi.listTrends()).length === 0) {
    for (const trend of trends) await meApi.createTrend(toDefinition(trend));
  }

  const notes = legacyNotes();
  if (notes.length > 0 && (await meApi.listNotes()).length === 0) {
    // Oldest first, so the server's ids follow the notes' own order.
    const oldestFirst = [...notes].sort((first, second) =>
      Date.parse(first.createdAt ?? "") - Date.parse(second.createdAt ?? ""));
    for (const note of oldestFirst) {
      await meApi.createNote({
        content: note.content.trim().slice(0, 10_000),
        created_at: validDate(note.createdAt),
        updated_at: validDate(note.updatedAt),
      });
    }
  }

  for (const key of keys) {
    try {
      window.localStorage.removeItem(key);
    } catch {
      // storage blocked: nothing to remove
    }
  }
}

/** Runs the import once per login; true when the app may load its pages (also after a failure). */
export function useBrowserDataImport(userId: string | undefined): boolean {
  const queryClient = useQueryClient();
  const [doneFor, setDoneFor] = useState<string | null>(null);
  const needsImport = Boolean(userId) && legacyKeys().length > 0;

  useEffect(() => {
    if (!userId || !needsImport || doneFor === userId) return;
    let cancelled = false;
    importBrowserData()
      .catch(error => console.warn("Could not copy this browser's saved data to your account", error))
      .finally(() => {
        if (cancelled) return;
        void queryClient.invalidateQueries({ queryKey: ["me"] });
        setDoneFor(userId);
      });
    return () => { cancelled = true; };
  }, [userId, needsImport, doneFor, queryClient]);

  return !needsImport || doneFor === userId;
}
