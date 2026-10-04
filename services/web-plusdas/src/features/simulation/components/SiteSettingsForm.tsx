import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { RunState, SiteConfig } from "@/api/types/powerflow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/shared/hooks/use-toast";
import { useProfiles, useRefreshPowerflow } from "../hooks/usePowerflow";
import { applySiteEdits, editsFromConfig, hasChanges, type ProfileChoice, type SiteEdits } from "../lib/siteEdits";

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

function ProfileRow({
  label,
  choice,
  scenarios,
  onChange,
}: {
  label: string;
  choice: ProfileChoice;
  scenarios: string[];
  onChange: (choice: ProfileChoice) => void;
}) {
  return (
    <div className="grid grid-cols-[1fr_14rem_7rem] items-end gap-3">
      <p className="text-sm text-foreground pb-2">{label}</p>
      <div className="space-y-1">
        <Label>Scenario</Label>
        <Select value={choice.scenario} onValueChange={(scenario) => onChange({ ...choice, scenario })}>
          <SelectTrigger aria-label={`${label} scenario`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {scenarios.map((scenario) => (
              <SelectItem key={scenario} value={scenario}>
                {scenario}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label>Scale</Label>
        <Input
          type="number"
          min={0}
          step={0.1}
          value={choice.scale}
          aria-label={`${label} scale`}
          onChange={(event) => onChange({ ...choice, scale: Number(event.target.value) })}
        />
      </div>
    </div>
  );
}

// Edits the selection fields of a stored site (simulation settings, profile scenarios, Modbus
// on/off) and saves the full config back. Assets, ratings and topology aren't editable here.
export function SiteSettingsForm({ siteName, config, isActive, runState }: Props) {
  const refresh = useRefreshPowerflow();
  const profiles = useProfiles();
  const [edits, setEdits] = useState<SiteEdits>(() => editsFromConfig(config));
  const [saveError, setSaveError] = useState<string | null>(null);
  const setSimulation = (patch: Partial<SiteEdits["simulation"]>) =>
    setEdits((current) => ({ ...current, simulation: { ...current.simulation, ...patch } }));

  const save = useMutation({
    mutationFn: () => powerflowApi.saveSite(siteName, applySiteEdits(config, edits)),
    onSuccess: () => {
      setSaveError(null);
      refresh();
      toast({
        title: `Saved ${siteName}`,
        description: isActive ? "The active site was reloaded and the simulation reset." : undefined,
      });
    },
    onError: (error) => setSaveError(getErrorMessage(error, "Saving the site failed")),
  });

  const blocked = isActive && runState !== undefined && runState !== "stopped";
  const loadScenarios = profiles.data?.load ?? [];
  const pvScenarios = profiles.data?.pv ?? [];
  const modbusChanged = edits.modbusEnabled !== (config.interfaces?.modbus?.enabled ?? false);

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
              <Input id="start_time" value={edits.simulation.start_time} onChange={(event) => setSimulation({ start_time: event.target.value })} />
            </div>
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
            <p className="text-xs text-muted-foreground">Takes effect when the site is (re)activated.</p>
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
          <Button className="gap-2" disabled={!hasChanges(config, edits) || blocked || save.isPending} onClick={() => save.mutate()}>
            <Save className="w-4 h-4" /> {save.isPending ? "Saving..." : "Save"}
          </Button>
          <Button variant="outline" disabled={save.isPending} onClick={() => setEdits(editsFromConfig(config))}>
            Discard changes
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
