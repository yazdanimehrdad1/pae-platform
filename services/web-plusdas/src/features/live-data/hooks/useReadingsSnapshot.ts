import { useQuery } from "@tanstack/react-query";
import { historianApi } from "@/api";
import { SNAPSHOT_READINGS } from "../lib/readingsSnapshot";

// The newest readings of every point of a device. Fetched when the device is selected, then only
// when the user takes a new snapshot (`refetch`): never on a timer or on window focus.
export function useReadingsSnapshot(siteId: string, deviceId: number | null) {
  return useQuery({
    queryKey: ["live-data-readings", siteId, deviceId],
    queryFn: () => historianApi.getRecentReadings(siteId, String(deviceId), SNAPSHOT_READINGS),
    enabled: deviceId !== null,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });
}
