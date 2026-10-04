import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { DeviceReadings, RunState } from "@/api/types/powerflow";
import { toast } from "@/shared/hooks/use-toast";

// React Query keys and reads for the Simulation page. Everything powerflow-side lives under
// the "powerflow" prefix, so a mutation can refresh it all with one invalidate.
export const powerflowKeys = {
  all: ["powerflow"] as const,
  status: ["powerflow", "status"] as const,
  sites: ["powerflow", "sites"] as const,
  site: (name: string) => ["powerflow", "site", name] as const,
  profiles: ["powerflow", "profiles"] as const,
  profileCsv: (folder: string, scenario: string) => ["powerflow", "profile", folder, scenario] as const,
  assets: ["powerflow", "assets"] as const,
  modbusRegisters: ["powerflow", "modbus-registers"] as const,
  conditions: ["powerflow", "conditions"] as const,
  devices: ["powerflow", "devices"] as const,
  deviceHistory: (device: string, points: string[]) => ["powerflow", "device-history", device, ...points] as const,
  snapshot: ["powerflow", "snapshot"] as const,
  eventScenarios: (site: string) => ["powerflow", "event-scenarios", site] as const,
};

const STATUS_POLL_MS = 2000;

export function useSimStatus() {
  return useQuery({
    queryKey: powerflowKeys.status,
    queryFn: powerflowApi.getStatus,
    refetchInterval: STATUS_POLL_MS,
    retry: false,
  });
}

export function useSites() {
  return useQuery({ queryKey: powerflowKeys.sites, queryFn: powerflowApi.listSites, retry: false });
}

export function useSite(name: string | undefined) {
  return useQuery({
    queryKey: powerflowKeys.site(name ?? ""),
    queryFn: () => powerflowApi.getSite(name as string),
    enabled: Boolean(name),
    retry: false,
  });
}

export function useProfiles() {
  return useQuery({ queryKey: powerflowKeys.profiles, queryFn: powerflowApi.listProfiles, retry: false });
}

/** Refresh everything powerflow-side after a change (site switch, save, delete, ...). */
export function useRefreshPowerflow() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: powerflowKeys.all });
}

/** Activate a stored site; powerflow needs the simulation stopped, so stop it first. */
export function useActivateSite(onDone?: (name: string) => void) {
  const refresh = useRefreshPowerflow();
  return useMutation({
    mutationFn: async ({ name, state }: { name: string; state: RunState | undefined }) => {
      if (state && state !== "stopped") await powerflowApi.stop();
      return powerflowApi.activateSite(name);
    },
    onSuccess: (_config, { name }) => {
      refresh();
      toast({ title: `Activated ${name}`, description: "The simulation is stopped: press Start to run it." });
      onDone?.(name);
    },
    onError: (error) =>
      toast({ title: "Activating the site failed", description: getErrorMessage(error), variant: "destructive" }),
  });
}

/** The injected conditions of the active site (polled like the status while shown). */
export function useConditions(enabled = true) {
  return useQuery({
    queryKey: powerflowKeys.conditions,
    queryFn: powerflowApi.getConditions,
    enabled,
    refetchInterval: STATUS_POLL_MS,
    retry: false,
  });
}

export function useEventScenarios(site: string | undefined) {
  return useQuery({
    queryKey: powerflowKeys.eventScenarios(site ?? ""),
    queryFn: () => powerflowApi.listEventScenarios(site as string),
    enabled: Boolean(site),
    retry: false,
  });
}

/** Run one powerflow call, then refresh everything; a failure is a toast titled `failureTitle`. */
export function usePowerflowCommand(failureTitle: string) {
  const refresh = useRefreshPowerflow();
  return useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: () => refresh(),
    onError: (error) => toast({ title: failureTitle, description: getErrorMessage(error), variant: "destructive" }),
  });
}

const HISTORY_POLL_MS = 5000;

/** Every device's standard points from the latest snapshot (polled while shown). */
export function useDevices(enabled: boolean) {
  return useQuery({
    queryKey: powerflowKeys.devices,
    queryFn: powerflowApi.listDevices,
    enabled,
    refetchInterval: STATUS_POLL_MS,
    retry: false,
  });
}

/** The chosen points of one device over the in-memory history (polled while shown). */
export function useDeviceHistory(device: DeviceReadings | undefined, points: string[]) {
  const label = device ? `${device.kind}.${device.asset_id}` : "";
  return useQuery({
    queryKey: powerflowKeys.deviceHistory(label, points),
    queryFn: () => powerflowApi.getDeviceHistory(device!.kind, device!.asset_id, points),
    enabled: Boolean(device) && points.length > 0,
    refetchInterval: HISTORY_POLL_MS,
    retry: false,
  });
}

/** The native snapshot, fetched only while `enabled` (e.g. the raw view is open). */
export function useLatestSnapshot(enabled: boolean) {
  return useQuery({
    queryKey: powerflowKeys.snapshot,
    queryFn: powerflowApi.getLatestSnapshot,
    enabled,
    refetchInterval: STATUS_POLL_MS,
    retry: false,
  });
}
