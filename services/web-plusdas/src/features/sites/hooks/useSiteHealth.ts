import { useQuery } from "@tanstack/react-query";
import { sitesApi } from "@/api";

// One site's health (GET /api/sites/{site_id}/health). The bar's counts and the open panel share
// this query: the panel renders from it at once, and refreshes it when the bar is opened.
export function useSiteHealth(siteId: string) {
  return useQuery({
    queryKey: ["site-health", siteId],
    queryFn: () => sitesApi.getHealth(siteId),
  });
}
