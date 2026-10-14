import { useQuery } from "@tanstack/react-query";
import { sitesApi } from "@/api";

// The Sites page refetches its stats (the sites list and each site's health) every 4 minutes.
export const SITE_STATS_REFRESH_MS = 4 * 60_000;

// One site's health (GET /api/sites/{site_id}/health), refetched every SITE_STATS_REFRESH_MS. The
// bar's counts and the open panel share this query: the panel renders from it at once, and
// refreshes it when the bar is opened.
export function useSiteHealth(siteId: string) {
  return useQuery({
    queryKey: ["site-health", siteId],
    queryFn: () => sitesApi.getHealth(siteId),
    refetchInterval: SITE_STATS_REFRESH_MS,
  });
}
