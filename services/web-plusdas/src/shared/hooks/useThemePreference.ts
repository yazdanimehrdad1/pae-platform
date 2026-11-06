import { useCallback, useEffect } from "react";
import { useTheme } from "@/shared/components/theme-provider";
import { PREFERENCE_KEYS, usePreference, usePreferences } from "@/shared/hooks/usePreference";

// Dark or light follows the logged-in user (a preference in intelli-gateway), dark when they
// never chose. The ThemeProvider still keeps the last one in this browser, only so the login page
// and the first paint after a reload show it before the preferences load.

type Theme = "dark" | "light";

export const DEFAULT_THEME: Theme = "dark";

const isTheme = (value: unknown): value is Theme => value === "dark" || value === "light";

/** The user's theme and a setter that shows it at once and saves it to their account. */
export function useThemePreference(): [Theme, (next: Theme) => void] {
  const { theme, setTheme } = useTheme();
  const [saved, save] = usePreference<Theme>(PREFERENCE_KEYS.theme, DEFAULT_THEME, isTheme);
  // Only a successful load decides: when it fails, the browser's last theme stays.
  const { isSuccess } = usePreferences();

  useEffect(() => {
    if (isSuccess && saved !== theme) setTheme(saved);
  }, [isSuccess, saved, theme, setTheme]);

  const choose = useCallback((next: Theme) => {
    setTheme(next);
    save(next);
  }, [setTheme, save]);

  return [theme, choose];
}
