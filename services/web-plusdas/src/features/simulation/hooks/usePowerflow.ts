import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { RunState } from "@/api/types/powerflow";
import { toast } from "@/shared/hooks/use-toast";

// React Query keys and reads for the Simulation page. Everything powerflow-side lives under
// the "powerflow" prefix, so a mutation can refresh it all with one invalidate.
export const powerflowKeys = {
  all: ["powerflow"] as const,
  status: ["powerflow", "status"] as const,
  sites: ["powerflow", "sites"] as const,
  site: (name: string) => ["powerflow", "site", name] as const,
  defaults: ["powerflow", "defaults"] as const,
  profiles: ["powerflow", "profiles"] as const,
  profileCsv: (folder: string, scenario: string) => ["powerflow", "profile", folder, scenario] as const,
  assets: ["powerflow", "assets"] as const,
  modbusRegisters: ["powerflow", "modbus-registers"] as const,
  modbusMaps: (site: string) => ["powerflow", "modbus-maps", site] as const,
  modbusMap: (site: string, asset: string) => ["powerflow", "modbus-map", site, asset] as const,
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

/** Refresh everything powerflow-side after a change (site switch, save, restore, ...). */
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
