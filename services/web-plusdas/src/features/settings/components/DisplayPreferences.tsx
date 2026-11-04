import { Switch } from "@/components/ui/switch";
import { BROWSER_TIME_ZONE, useDisplayTimeZone } from "@/shared/hooks/useDisplayTimeZone";
import { useThemePreference } from "@/shared/hooks/useThemePreference";

// The user's display preferences, saved to their account: the same ones as the sidebar's
// sun/moon button and the "My time" switch on the pages that show times (they stay in sync).
export function DisplayPreferences() {
  const [theme, setTheme] = useThemePreference();
  const { display, setDisplay } = useDisplayTimeZone(null);
  return (
    <div className="space-y-3">
      <label className="flex items-center justify-between gap-4 rounded-lg bg-muted/20 p-4">
        <span>
          <span className="block text-sm font-medium text-foreground">Dark mode</span>
          <span className="block text-xs text-muted-foreground">Dark unless you turn it off.</span>
        </span>
        <Switch checked={theme === "dark"} onCheckedChange={checked => setTheme(checked ? "dark" : "light")} aria-label="Dark mode" />
      </label>
      <label className="flex items-center justify-between gap-4 rounded-lg bg-muted/20 p-4">
        <span>
          <span className="block text-sm font-medium text-foreground">Show times in my time zone</span>
          <span className="block text-xs text-muted-foreground">
            Off: each site's own time zone. On: yours ({BROWSER_TIME_ZONE}). Applies to every page.
          </span>
        </span>
        <Switch checked={display === "browser"} onCheckedChange={checked => setDisplay(checked ? "browser" : "site")} aria-label="Show times in my time zone" />
      </label>
    </div>
  );
}
