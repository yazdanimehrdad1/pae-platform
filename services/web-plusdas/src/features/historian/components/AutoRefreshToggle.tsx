import { Timer, TimerOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { AUTO_REFRESH_MS } from "../hooks/useHistorianSeries";

const EVERY = `${AUTO_REFRESH_MS / 60_000} min`;

/** Turns the charts' automatic refresh (every minute) on or off. Off by default: the charts then
 * refresh only when Refresh is clicked. */
export function AutoRefreshToggle({ enabled, onChange }: { enabled: boolean; onChange: (enabled: boolean) => void }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant={enabled ? "default" : "outline"}
            size="sm"
            className="gap-2"
            aria-pressed={enabled}
            onClick={() => onChange(!enabled)}
          >
            {enabled ? <Timer className="w-4 h-4" /> : <TimerOff className="w-4 h-4" />}
            {enabled ? `Auto refresh: every ${EVERY}` : "Auto refresh: off"}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{enabled ? "Stop refreshing the charts on their own" : `Refresh the charts every ${EVERY} on their own`}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
