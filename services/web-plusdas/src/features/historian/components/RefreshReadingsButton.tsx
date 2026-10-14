import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { isHistorianQueryOf } from "../hooks/useHistorianSeries";

/**
 * Refetches the readings of every trend chart on the page (all `useHistorianSeries` queries of the
 * site: points and site functions). A preset window is resolved to "now" by backend-ot, so this
 * pulls the newest samples.
 */
export function RefreshReadingsButton({ siteId }: { siteId: string | null }) {
  const queryClient = useQueryClient();
  const predicate = isHistorianQueryOf(siteId);
  const isRefreshing = useIsFetching({ predicate }) > 0;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              disabled={!siteId || isRefreshing}
              onClick={() => queryClient.invalidateQueries({ predicate })}
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
              {isRefreshing ? "Refreshing…" : "Refresh"}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent><p>Fetch the latest readings for the selected points</p></TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
