import { Clock } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { BROWSER_TIME_ZONE, type TimeDisplay } from "@/shared/hooks/useDisplayTimeZone";

/** "Times in America/Los_Angeles (site)", and a switch to the user's own zone when it differs. */
export function TimeZoneToggle({ siteTimeZone, display, onDisplayChange }: {
  siteTimeZone: string | null;
  display: TimeDisplay;
  onDisplayChange: (display: TimeDisplay) => void;
}) {
  const differs = siteTimeZone !== null && siteTimeZone !== BROWSER_TIME_ZONE;
  const showsBrowser = display === "browser" || siteTimeZone === null;
  const shown = showsBrowser ? BROWSER_TIME_ZONE : siteTimeZone;
  return (
    <div className="flex items-center gap-3 text-sm text-muted-foreground print:hidden">
      <span className="inline-flex items-center gap-1.5">
        <Clock aria-hidden className="h-4 w-4" />
        Times in {shown} {differs && (showsBrowser ? "(your time)" : "(site time)")}
      </span>
      {differs && (
        <label className="inline-flex items-center gap-2">
          <Switch checked={display === "browser"} onCheckedChange={checked => onDisplayChange(checked ? "browser" : "site")} aria-label="Show times in my time zone" />
          My time
        </label>
      )}
    </div>
  );
}
