import { useState } from "react";
import { Eraser } from "lucide-react";
import { powerflowApi } from "@/api";
import type { CommTarget, ConditionChange, ConditionsReport, FaultCause, SiteConfig } from "@/api/types/powerflow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { usePowerflowCommand } from "../../hooks/usePowerflow";
import { causesFor } from "../../lib/scenarioEdits";

interface Props {
  config: SiteConfig;
  report: ConditionsReport | undefined;
  enabled: boolean; // only the active site's conditions can be changed
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1">
      <span className="text-sm text-foreground">{label}</span>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

function GridValue({
  id,
  label,
  unit,
  current,
  disabled,
  onApply,
}: {
  id: string;
  label: string;
  unit: string;
  current: number | null | undefined;
  disabled: boolean;
  onApply: (value: number | null) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>
        {label} ({unit}){current != null ? `: ${current} now` : ": as configured"}
      </Label>
      <div className="flex gap-2">
        <Input id={id} type="number" step={0.01} className="w-28" value={value} onChange={(event) => setValue(event.target.value)} />
        <Button size="sm" variant="outline" disabled={disabled || value === ""} onClick={() => onApply(Number(value))}>
          Apply
        </Button>
        <Button size="sm" variant="ghost" disabled={disabled || current == null} onClick={() => onApply(null)}>
          Restore
        </Button>
      </div>
    </div>
  );
}

// Live toggles for the active site: breakers, asset faults, comm loss and grid events. Each
// change is applied at once (the next step sees it).
export function LiveConditions({ config, report, enabled }: Props) {
  const command = usePowerflowCommand("Changing the conditions failed");
  const apply = (change: ConditionChange) => command.mutate(() => powerflowApi.applyCondition(change));
  const [causes, setCauses] = useState<Record<string, FaultCause>>({});
  const disabled = !enabled || command.isPending;

  // Without live conditions (site not active), the config's initial positions.
  const breakers = report?.breakers ?? [
    { id: "poi", kind: "poi" as const, closed: config.poi?.breaker?.closed ?? true },
    ...(config.bess ?? []).map((bess) => ({ id: bess.id, kind: "bess" as const, closed: bess.breaker?.closed ?? true })),
    ...(config.pv ?? []).map((pv) => ({ id: pv.id, kind: "pv" as const, closed: pv.breaker?.closed ?? true })),
    ...(config.loads ?? []).map((load) => ({ id: load.id, kind: "load" as const, closed: load.breaker?.closed ?? true })),
  ];
  const faults = new Map((report?.faults ?? []).map((fault) => [fault.asset_id, fault.cause]));
  const lost = new Set((report?.comm_loss ?? []).map((item) => `${item.target}:${item.id ?? ""}`));
  const faultable = [
    ...(config.bess ?? []).map((bess) => ({ id: bess.id, kind: "BESS" })),
    ...(config.pv ?? []).map((pv) => ({ id: pv.id, kind: "PV" })),
  ];
  const commTargets: { target: CommTarget; id: string | null; label: string }[] = [
    ...[...(config.bess ?? []), ...(config.pv ?? []), ...(config.loads ?? [])].map((asset) => ({
      target: "asset" as const,
      id: asset.id,
      label: asset.name ?? asset.id,
    })),
    ...(config.meters ?? []).map((meter) => ({ target: "meter" as const, id: meter.id, label: `meter ${meter.name ?? meter.id}` })),
    { target: "poi_meter", id: null, label: "POI meter" },
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>Live conditions</CardTitle>
          <CardDescription>
            {enabled
              ? "Inject a condition into the running simulation now. The next step applies it."
              : "Activate this site to inject conditions."}
          </CardDescription>
        </div>
        <Button size="sm" variant="outline" className="gap-1" disabled={disabled} onClick={() => command.mutate(powerflowApi.clearConditions)}>
          <Eraser className="w-4 h-4" /> Clear all
        </Button>
      </CardHeader>
      <CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <h3 className="font-semibold text-foreground mb-2">Breakers</h3>
          {breakers.map((breaker) => (
            <Row key={breaker.id} label={breaker.id === "poi" ? "POI (whole site)" : `${breaker.kind.toUpperCase()} ${breaker.id}`}>
              <span className="text-xs text-muted-foreground">{breaker.closed ? "closed" : "open"}</span>
              <Switch
                checked={breaker.closed}
                disabled={disabled}
                aria-label={`Breaker ${breaker.id} closed`}
                onCheckedChange={(closed) => apply({ type: "breaker", breaker: breaker.id, closed })}
              />
            </Row>
          ))}
        </section>

        <section>
          <h3 className="font-semibold text-foreground mb-2">Asset faults</h3>
          {faultable.map(({ id, kind }) => {
            const active = faults.get(id);
            const cause = active ?? causes[id] ?? "trip";
            return (
              <Row key={id} label={`${kind} ${id}`}>
                <Select
                  value={cause}
                  disabled={disabled || active !== undefined}
                  onValueChange={(value) => setCauses((current) => ({ ...current, [id]: value as FaultCause }))}
                >
                  <SelectTrigger className="w-40" aria-label={`Fault cause ${id}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {causesFor(id, config).map((option) => (
                      <SelectItem key={option} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Switch
                  checked={active !== undefined}
                  disabled={disabled}
                  aria-label={`Fault ${id}`}
                  onCheckedChange={(on) => apply({ type: "asset_fault", asset_id: id, active: on, cause })}
                />
              </Row>
            );
          })}
        </section>

        <section>
          <h3 className="font-semibold text-foreground mb-2">Communication loss</h3>
          {commTargets.map(({ target, id, label }) => {
            const isLost = lost.has(`${target}:${id ?? ""}`);
            return (
              <Row key={`${target}:${id}`} label={label}>
                <span className="text-xs text-muted-foreground">{isLost ? "lost: values frozen" : "ok"}</span>
                <Switch
                  checked={isLost}
                  disabled={disabled}
                  aria-label={`Comm loss ${label}`}
                  onCheckedChange={(active) => apply({ type: "comm_loss", target, id, active })}
                />
              </Row>
            );
          })}
        </section>

        <section className="space-y-3">
          <h3 className="font-semibold text-foreground">Grid</h3>
          <GridValue
            id="grid_vm_pu"
            label="Source voltage"
            unit="pu, 0.5–1.5"
            current={report?.grid_vm_pu}
            disabled={disabled}
            onApply={(vm_pu) => apply({ type: "grid_voltage", vm_pu })}
          />
          <GridValue
            id="grid_hz"
            label="Frequency"
            unit="Hz, 55–65"
            current={report?.grid_hz}
            disabled={disabled}
            onApply={(hz) => apply({ type: "grid_frequency", hz })}
          />
        </section>
      </CardContent>
    </Card>
  );
}
