import { useState } from "react";
import { powerflowApi } from "@/api";
import type { BessBatteryRequest, BessBatteryState, SiteConfig } from "@/api/types/powerflow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBessBatteries, usePowerflowCommand } from "../../hooks/usePowerflow";

const MIN_ROUND_TRIP_PCT = 50;

interface Props {
  config: SiteConfig;
  enabled: boolean; // only the active site's BESS can be changed
}

interface RowDraft {
  soc: string;
  roundTrip: string | null; // null = not edited (shows the value in effect)
}

function isWithin(text: string, min: number, max: number): boolean {
  const value = Number(text);
  return text.trim() !== "" && Number.isFinite(value) && value >= min && value <= max;
}

function efficiencyLabel(battery: BessBatteryState): string {
  if (battery.round_trip_efficiency_pct != null) return `${battery.round_trip_efficiency_pct} %`;
  const roundTrip = battery.eta_charge * battery.eta_discharge * 100;
  return `site config (${roundTrip.toFixed(1)} %)`;
}

// Battery overrides of the active site: set a BESS's SOC now (e.g. jump to a low SOC to test an
// edge) and its round-trip efficiency. Every BESS is back at 100 % after an activate or a reset.
// Works while auto dispatch drives the BESS.
export function BatteryCard({ config, enabled }: Props) {
  const bessIds = (config.bess ?? []).map((bess) => bess.id);
  const batteries = useBessBatteries(bessIds, enabled).data;
  const command = usePowerflowCommand("Changing the battery failed");
  const [drafts, setDrafts] = useState<Record<string, RowDraft>>({});
  const disabled = !enabled || command.isPending;
  const batteryById = new Map((batteries ?? []).map((battery) => [battery.asset_id, battery]));

  const draftOf = (id: string): RowDraft => drafts[id] ?? { soc: "", roundTrip: null };
  const updateDraft = (id: string, change: Partial<RowDraft>) =>
    setDrafts((current) => ({ ...current, [id]: { ...draftOf(id), ...change } }));
  const send = (id: string, request: BessBatteryRequest, reset: Partial<RowDraft>) =>
    command.mutate(() => powerflowApi.setBessBattery(id, request), { onSuccess: () => updateDraft(id, reset) });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Battery</CardTitle>
        <CardDescription>
          {enabled
            ? "Set a BESS's SOC now, or its round-trip efficiency (until the next activate or reset, which return every BESS to 100 %)."
            : "Activate this site to change its batteries."}
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>BESS</TableHead>
              <TableHead>SOC now</TableHead>
              <TableHead>Set SOC %</TableHead>
              <TableHead>Round-trip efficiency %</TableHead>
              <TableHead>In effect</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bessIds.map((id) => {
              const battery = batteryById.get(id);
              const draft = draftOf(id);
              const roundTripText = draft.roundTrip ?? String(battery?.round_trip_efficiency_pct ?? "");
              return (
                <TableRow key={id} data-battery-bess={id}>
                  <TableCell>{id}</TableCell>
                  <TableCell>{battery ? `${battery.soc_pct.toFixed(1)} %` : "–"}</TableCell>
                  <TableCell className="p-1">
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        aria-label={`${id} set SOC %`}
                        className="h-8 w-20"
                        value={draft.soc}
                        disabled={disabled}
                        onChange={(event) => updateDraft(id, { soc: event.target.value })}
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={disabled || !isWithin(draft.soc, 0, 100)}
                        onClick={() => send(id, { soc_pct: Number(draft.soc) }, { soc: "" })}
                      >
                        Set
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell className="p-1">
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={MIN_ROUND_TRIP_PCT}
                        max={100}
                        aria-label={`${id} round-trip efficiency %`}
                        className="h-8 w-20"
                        placeholder="site config"
                        value={roundTripText}
                        disabled={disabled}
                        onChange={(event) => updateDraft(id, { roundTrip: event.target.value })}
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={disabled || draft.roundTrip === null || !isWithin(draft.roundTrip, MIN_ROUND_TRIP_PCT, 100)}
                        onClick={() =>
                          send(id, { round_trip_efficiency_pct: Number(draft.roundTrip) }, { roundTrip: null })
                        }
                      >
                        Apply
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={disabled || battery?.round_trip_efficiency_pct == null}
                        onClick={() => send(id, { round_trip_efficiency_pct: null }, { roundTrip: null })}
                      >
                        Use site config
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {battery ? efficiencyLabel(battery) : "–"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
