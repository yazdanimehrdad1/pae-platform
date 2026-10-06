import { useQuery } from "@tanstack/react-query";

import { fetchSites } from "@/api/backendOt";
import { queryKeys } from "@/api/queryKeys";

/** The sites in backend-ot, by name. They change rarely. */
export function useSites() {
  return useQuery({
    queryKey: queryKeys.sites,
    queryFn: fetchSites,
    staleTime: 60_000,
    select: (sites) => [...sites].sort((a, b) => a.name.localeCompare(b.name)),
  });
}
