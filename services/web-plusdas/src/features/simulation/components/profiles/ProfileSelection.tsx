import { Save } from "lucide-react";
import { getErrorMessage } from "@/api/client";
import type { RunState, SiteConfig } from "@/api/types/powerflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useActiveConfig, useSaveSite } from "../../hooks/usePowerflow";
import type { useSiteEdits } from "../../hooks/useSiteEdits";
import { applySiteEdits, type ProfileChoice } from "../../lib/siteEdits";
import { ProfileRow } from "./ProfileRow";

interface Props {
  siteName: string;
  config: SiteConfig;
  isActive: boolean;
  runState: RunState | undefined;
  loadScenarios: string[];
  pvScenarios: string[];
  siteEdits: ReturnType<typeof useSiteEdits>;
}

// Which profile each load and PV of the selected site follows. The badge is what the engine is
// simulating right now (GET /config), so it shows what the run really uses. Saving writes the
// site config; the active site has to be stopped for that, and the save reloads and resets it.
export function ProfileSelection({ siteName, config, isActive, runState, loadScenarios, pvScenarios, siteEdits }: Props) {
  const { edits, setEdits, reset, dirty } = siteEdits;
  const activeConfig = useActiveConfig(isActive).data;
  const save = useSaveSite(siteName, isActive);
  const running = isActive && runState !== undefined && runState !== "stopped";

  const simulating = (scenario: string | undefined) =>
    isActive ? (
      <Badge variant="secondary" className="font-normal">
        simulating: {scenario ?? "…"}
      </Badge>
    ) : (
      <Badge variant="outline" className="font-normal text-muted-foreground">
        not active
      </Badge>
    );
  const setLoad = (id: string, choice: ProfileChoice) =>
    setEdits((current) => ({ ...current, loadProfiles: { ...current.loadProfiles, [id]: choice } }));
  const setPv = (id: string, choice: ProfileChoice) =>
    setEdits((current) => ({ ...current, pvProfiles: { ...current.pvProfiles, [id]: choice } }));
  const submit = () =>
    save.mutate({ config: applySiteEdits(config, edits), stopFirst: running, restart: runState === "running" });

  return (
    <Card data-profile-selection>
      <CardHeader>
        <CardTitle>Profile selection</CardTitle>
        <CardDescription>Pick which profile each load and PV of {siteName} follows, then save.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {(config.loads ?? []).map((load) => (
          <ProfileRow
            key={load.id}
            label={`Load ${load.name ?? load.id}`}
            badge={simulating(activeConfig?.loads?.find((item) => item.id === load.id)?.profile.scenario)}
            choice={edits.loadProfiles[load.id]}
            scenarios={loadScenarios}
            disabled={save.isPending}
            onChange={(choice) => setLoad(load.id, choice)}
          />
        ))}
        {(config.pv ?? []).map((pv) => (
          <ProfileRow
            key={pv.id}
            label={`PV ${pv.name ?? pv.id} (${pv.availability.source ?? "ac_kw"})`}
            badge={simulating(activeConfig?.pv?.find((item) => item.id === pv.id)?.availability.scenario)}
            choice={edits.pvProfiles[pv.id]}
            scenarios={pvScenarios}
            disabled={save.isPending}
            onChange={(choice) => setPv(pv.id, choice)}
          />
        ))}
        {(config.loads?.length ?? 0) + (config.pv?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">This site has no loads or PV.</p>
        )}
        {dirty && (
          <p className="text-xs text-muted-foreground">
            {isActive
              ? `Saving reloads the active site and resets the simulation${running ? " (it is stopped first" + (runState === "running" ? ", then started again)" : ")") : ""}.`
              : "Takes effect when the site is activated."}
          </p>
        )}
        {save.isError && (
          <p role="alert" className="text-sm rounded-md border border-destructive/40 bg-destructive/10 p-3 text-destructive">
            {getErrorMessage(save.error, "Saving the profiles failed")}
          </p>
        )}
        <div className="flex gap-2">
          <Button className="gap-2" disabled={!dirty || save.isPending} onClick={submit}>
            <Save className="w-4 h-4" /> {save.isPending ? "Saving..." : running ? "Stop & save" : "Save"}
          </Button>
          <Button variant="outline" disabled={!dirty || save.isPending} onClick={reset}>
            Discard changes
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
