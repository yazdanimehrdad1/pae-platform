import { useState } from "react";
import { powerflowApi } from "@/api";
import type { AutoDispatchBess, AutoDispatchPhase, SiteConfig } from "@/api/types/powerflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAutoDispatch, usePowerflowCommand } from "../../hooks/usePowerflow";
import {
  type AutoDispatchDraft,
  type SettingField,
  type SettingsDraft,
  type StartChoice,
  draftFromReport,
  isDraftValid,
  requestFromDraft,
} from "../../lib/autoDispatchDraft";

const PHASE_LABELS: Record<AutoDispatchPhase, string> = {
  charging: "Charging",
  discharging: "Discharging",
  resting: "Resting",
};

const START_LABELS: Record<StartChoice, string> = {
  auto: "Auto",
  charge: "Charge",
  discharge: "Discharge",
};

const COLUMNS: { field: SettingField; label: string }[] = [
  { field: "soc_low_pct", label: "SOC low %" },
  { field: "soc_high_pct", label: "SOC high %" },
  { field: "rest_s", label: "Rest s" },
  { field: "p_noise_std_pct", label: "Noise std %" },
  { field: "ramp_kw_per_s", label: "Ramp kW/s" },
  { field: "q_kvar", label: "Q kvar" },
];

interface Props {
  config: SiteConfig;
  enabled: boolean; // only the active site can be auto dispatched
}

function SettingsCells({
  rowLabel,
  settings,
  placeholders,
  disabled,
  onChange,
}: {
  rowLabel: string;
  settings: SettingsDraft;
  placeholders: Record<SettingField, string>;
  disabled: boolean;
  onChange: (settings: SettingsDraft) => void;
}) {
  return (
    <>
      {COLUMNS.map(({ field, label }) => (
        <TableCell key={field} className="p-1">
          <Input
            type="number"
            aria-label={`${rowLabel} ${label}`}
            className="h-8 w-20"
            placeholder={placeholders[field]}
            value={settings.values[field]}
            disabled={disabled}
            onChange={(event) => onChange({ ...settings, values: { ...settings.values, [field]: event.target.value } })}
          />
        </TableCell>
      ))}
      <TableCell className="p-1">
        <Select value={settings.start} disabled={disabled} onValueChange={(start) => onChange({ ...settings, start: start as StartChoice })}>
          <SelectTrigger aria-label={`${rowLabel} start direction`} className="h-8 w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(START_LABELS) as StartChoice[]).map((choice) => (
              <SelectItem key={choice} value={choice}>
                {START_LABELS[choice]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
    </>
  );
}

function Status({ row }: { row: AutoDispatchBess | undefined }) {
  if (!row) return null;
  if (!row.included || !row.phase) return <span className="text-xs text-muted-foreground">manual setpoints</span>;
  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <Badge variant="outline">{PHASE_LABELS[row.phase]}</Badge>
      <span className="text-xs text-muted-foreground">
        SOC {row.soc_pct.toFixed(1)} % · {row.soc_low_pct}–{row.soc_high_pct} %
        {row.rest_remaining_s != null && ` · ${Math.ceil(row.rest_remaining_s)} s left`}
      </span>
    </div>
  );
}

// Auto dispatch: each BESS of the active site cycles inside its SOC window on its own, so the
// simulation runs without anyone writing setpoints. The Defaults row applies to every BESS; a
// BESS row overrides only what is filled in (blank = the default, shown greyed).
export function AutoDispatchCard({ config, enabled }: Props) {
  const report = useAutoDispatch(enabled).data;
  const command = usePowerflowCommand("Changing auto dispatch failed");
  const bessIds = (config.bess ?? []).map((bess) => bess.id);
  const [edited, setEdited] = useState<AutoDispatchDraft | null>(null);
  const draft = edited ?? draftFromReport(report, bessIds);
  const isOn = enabled && Boolean(report?.enabled);
  const disabled = !enabled || command.isPending;
  const valid = isDraftValid(draft);
  const rowsById = new Map((report?.bess ?? []).map((row) => [row.asset_id, row]));

  const send = (on: boolean) =>
    command.mutate(() => powerflowApi.setAutoDispatch(requestFromDraft(draft, on)), {
      onSuccess: () => setEdited(null),
    });
  const update = (change: Partial<AutoDispatchDraft>) => setEdited({ ...draft, ...change });
  const updateBess = (id: string, settings: SettingsDraft) => update({ bess: { ...draft.bess, [id]: settings } });

  // A default's placeholder is powerflow's built-in value; a BESS's is what it falls back to.
  const builtIn = (field: SettingField, bessId?: string): string => {
    const battery = (config.bess ?? []).find((bess) => bess.id === bessId)?.battery;
    if (field === "soc_low_pct") return bessId ? String(battery?.soc_min_pct ?? 5) : "battery min";
    if (field === "soc_high_pct") return bessId ? String(battery?.soc_max_pct ?? 95) : "battery max";
    if (field === "ramp_kw_per_s") return "none";
    return "0";
  };
  const placeholdersFor = (bessId?: string) =>
    Object.fromEntries(
      COLUMNS.map(({ field }) => [
        field,
        bessId && draft.defaults.values[field] !== "" ? draft.defaults.values[field] : builtIn(field, bessId),
      ]),
    ) as Record<SettingField, string>;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>Auto dispatch</CardTitle>
          <CardDescription>
            {enabled
              ? "Each included BESS discharges down to its window's low SOC, rests, charges up to its high SOC, rests, and repeats. Its setpoints are locked while it runs; leaving auto dispatch leaves it idle."
              : "Activate this site to auto dispatch its BESS."}
          </CardDescription>
        </div>
        <Switch checked={isOn} disabled={disabled || !valid} aria-label="Auto dispatch" onCheckedChange={send} />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-4">
          <div className="space-y-1">
            <Label htmlFor="auto-dispatch-power">Power (% of each BESS's rating)</Label>
            <Input
              id="auto-dispatch-power"
              type="number"
              min={1}
              max={100}
              className="w-28"
              value={draft.powerPct}
              disabled={disabled}
              onChange={(event) => update({ powerPct: event.target.value })}
            />
          </div>
          {isOn && (
            <Button size="sm" variant="outline" disabled={disabled || edited === null || !valid} onClick={() => send(true)}>
              Apply changes
            </Button>
          )}
        </div>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>BESS</TableHead>
                <TableHead>Include</TableHead>
                {COLUMNS.map(({ field, label }) => (
                  <TableHead key={field}>{label}</TableHead>
                ))}
                <TableHead>Start</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow data-auto-dispatch-defaults>
                <TableCell className="font-medium">Defaults</TableCell>
                <TableCell />
                <SettingsCells
                  rowLabel="Defaults"
                  settings={draft.defaults}
                  placeholders={placeholdersFor()}
                  disabled={disabled}
                  onChange={(defaults) => update({ defaults })}
                />
                <TableCell />
              </TableRow>
              {bessIds.map((id) => {
                const settings = draft.bess[id] ?? draftFromReport(undefined, [id]).bess[id];
                return (
                  <TableRow key={id} data-auto-dispatch-bess={id}>
                    <TableCell>{id}</TableCell>
                    <TableCell>
                      <Switch
                        checked={settings.included}
                        disabled={disabled}
                        aria-label={`Include ${id}`}
                        onCheckedChange={(included) => updateBess(id, { ...settings, included })}
                      />
                    </TableCell>
                    <SettingsCells
                      rowLabel={id}
                      settings={settings}
                      placeholders={placeholdersFor(id)}
                      disabled={disabled || !settings.included}
                      onChange={(changed) => updateBess(id, changed)}
                    />
                    <TableCell>{isOn && <Status row={rowsById.get(id)} />}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
