import { Save } from "lucide-react";
import { getErrorMessage } from "@/api/client";
import type { RunState, SiteConfig } from "@/api/types/powerflow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useProfiles, useSaveSite } from "../hooks/usePowerflow";
import { useSiteEdits } from "../hooks/useSiteEdits";
import { applySiteEdits, type SiteEdits } from "../lib/siteEdits";
import { ProfileRow } from "./profiles/ProfileRow";

interface Props {
  siteName: string;
  config: SiteConfig;
  isActive: boolean;
  runState: RunState | undefined;
}

function NumberField({
  id,
  label,
  value,
  step,
  min,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  step?: number;
  min?: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" value={value} step={step} min={min} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  );
}

// Edits the selection fields of a stored site (simulation settings, profile scenarios, Modbus
// on/off) and saves the full config back. Assets, ratings and topology aren't editable here.
export function SiteSettingsForm({ siteName, config, isActive, runState }: Props) {
  const profiles = useProfiles();
  const { edits, setEdits, reset, dirty } = useSiteEdits(config);
  const setSimulation = (patch: Partial<SiteEdits["simulation"]>) =>
    setEdits((current) => ({ ...current, simulation: { ...current.simulation, ...patch } }));

  const save = useSaveSite(siteName, isActive);
  const saveError = save.isError ? getErrorMessage(save.error, "Saving the site failed") : null;

  const blocked = isActive && runState !== undefined && runState !== "stopped";
  const loadScenarios = profiles.data?.load ?? [];
  const pvScenarios = profiles.data?.pv ?? [];
  const modbusChanged = edits.modbusEnabled !== (config.interfaces?.modbus?.enabled ?? false);
  const startsNow = edits.simulation.start_time === "now";
  const configuredStart = config.simulation?.start_time;
  const fixedStart = configuredStart && configuredStart !== "now" ? configuredStart : "2026-01-01T00:00:00Z";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Site settings</CardTitle>
        <CardDescription>
          Choose the simulation settings and which existing profile each asset follows. Devices, ratings and the
          network can't be changed here.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <section className="space-y-3">
          <h3 className="font-semibold text-foreground">Simulation</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <NumberField id="step_s" label="Step (s)" value={edits.simulation.step_s} step={0.5} min={0.1} onChange={(step_s) => setSimulation({ step_s })} />
            <div className="space-y-1">
              <Label htmlFor="start_time">Start time (UTC, ISO 8601)</Label>
              <Input
                id="start_time"
                value={edits.simulation.start_time}
                disabled={startsNow}
                onChange={(event) => setSimulation({ start_time: event.target.value })}
              />
              <div className="flex items-center gap-2 pt-1">
                <Switch
                  id="start_now"
                  checked={startsNow}
                  onCheckedChange={(now) => setSimulation({ start_time: now ? "now" : fixedStart })}
                />
                <Label htmlFor="start_now" className="text-xs text-muted-foreground">
                  Now (the wall clock when a run starts fresh or is reset)
                </Label>
              </div>
            </div>
            <NumberField id="speed" label="Speed (× real time, up to 100)" value={edits.simulation.speed} step={1} min={0.1} onChange={(speed) => setSimulation({ speed })} />
            <NumberField id="start_step" label="Start step" value={edits.simulation.start_step} step={1} min={0} onChange={(start_step) => setSimulation({ start_step })} />
            <NumberField id="seed" label="Seed" value={edits.simulation.seed} min={0} onChange={(seed) => setSimulation({ seed })} />
            <NumberField id="history_size" label="History size (snapshots)" value={edits.simulation.history_size} min={1} onChange={(history_size) => setSimulation({ history_size })} />
            <div className="flex items-center gap-2 pt-6">
              <Switch id="autostart" checked={edits.simulation.autostart} onCheckedChange={(autostart) => setSimulation({ autostart })} />
              <Label htmlFor="autostart">Autostart</Label>
            </div>
            <div className="flex items-center gap-2 pt-6">
              <Switch id="test_mode" checked={edits.simulation.test_mode} onCheckedChange={(test_mode) => setSimulation({ test_mode })} />
              <Label htmlFor="test_mode">Test mode (manual stepping)</Label>
            </div>
          </div>
        </section>

        {(config.loads?.length ?? 0) + (config.pv?.length ?? 0) > 0 && (
          <section className="space-y-3">
            <h3 className="font-semibold text-foreground">Profiles</h3>
            {(config.loads ?? []).map((load) => (
              <ProfileRow
                key={load.id}
                label={`Load ${load.name ?? load.id}`}
                choice={edits.loadProfiles[load.id]}
                scenarios={loadScenarios}
                onChange={(choice) => setEdits((current) => ({ ...current, loadProfiles: { ...current.loadProfiles, [load.id]: choice } }))}
              />
            ))}
            {(config.pv ?? []).map((pv) => (
              <ProfileRow
                key={pv.id}
                label={`PV ${pv.name ?? pv.id} (${pv.availability.source ?? "ac_kw"})`}
                choice={edits.pvProfiles[pv.id]}
                scenarios={pvScenarios}
                onChange={(choice) => setEdits((current) => ({ ...current, pvProfiles: { ...current.pvProfiles, [pv.id]: choice } }))}
              />
            ))}
          </section>
        )}

        <section className="space-y-2">
          <h3 className="font-semibold text-foreground">Interfaces</h3>
          <div className="flex items-center gap-2">
            <Switch id="modbus" checked={edits.modbusEnabled} onCheckedChange={(modbusEnabled) => setEdits((current) => ({ ...current, modbusEnabled }))} />
            <Label htmlFor="modbus">Modbus TCP server</Label>
          </div>
          {modbusChanged && (
            <p className="text-xs text-muted-foreground">
              {isActive ? "Saving restarts the active site's interfaces." : "Takes effect when the site is activated."}
            </p>
          )}
        </section>

        {blocked && (
          <p role="alert" className="text-sm rounded-md border border-warning/40 bg-warning/10 p-3 text-foreground">
            This is the active site and the simulation is {runState}. Stop it before saving: saving reloads the site and
            resets the simulation.
          </p>
        )}
        {saveError && (
          <p role="alert" className="text-sm rounded-md border border-destructive/40 bg-destructive/10 p-3 text-destructive">
            {saveError}
          </p>
        )}
        <div className="flex gap-2">
          <Button className="gap-2" disabled={!dirty || blocked || save.isPending} onClick={() => save.mutate({ config: applySiteEdits(config, edits) })}>
            <Save className="w-4 h-4" /> {save.isPending ? "Saving..." : "Save"}
          </Button>
          <Button variant="outline" disabled={save.isPending} onClick={reset}>
            Discard changes
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
