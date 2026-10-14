import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { CommTarget, EventScenario, FaultCause, FaultCauseInfo, SiteConfig } from "@/api/types/powerflow";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/shared/hooks/use-toast";
import { useFaultCauses, useRefreshPowerflow } from "../../hooks/usePowerflow";
import {
  CHANGE_LABELS,
  blankExpectedRow,
  blankRow,
  causesFor,
  deviceLabels,
  expectedRowFrom,
  expectedRowProblems,
  rowFromEvent,
  rowProblems,
  scenarioFromRows,
  targetsFor,
  type ChangeType,
  type EventRow,
  type ExpectedRow,
} from "../../lib/scenarioEdits";

interface Props {
  siteName: string;
  config: SiteConfig;
  // null = a new scenario
  editing: { name: string; scenario: EventScenario } | null;
  // A new scenario prefilled from another (a built-in is read-only: duplicate it to change it).
  copyOf?: { name: string; scenario: EventScenario };
  open: boolean;
  onClose: () => void;
}

const NAME_PATTERN = /^[a-z0-9_-]+$/;

function Choice<T extends string>({
  label,
  value,
  options,
  onChange,
  width = "w-36",
}: {
  label: string;
  value: T;
  options: readonly T[] | { value: T; label: string }[];
  onChange: (value: T) => void;
  width?: string;
}) {
  const items = options.map((option) => (typeof option === "string" ? { value: option, label: option } : option));
  return (
    <Select value={value} onValueChange={(next) => onChange(next as T)}>
      <SelectTrigger className={width} aria-label={label}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {items.map((item) => (
          <SelectItem key={item.value} value={item.value}>
            {item.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function EventRowFields({
  row,
  index,
  config,
  catalog,
  onChange,
  onRemove,
}: {
  row: EventRow;
  index: number;
  config: SiteConfig;
  catalog: FaultCauseInfo[];
  onChange: (row: EventRow) => void;
  onRemove: () => void;
}) {
  const patch = (update: Partial<EventRow>) => onChange({ ...row, ...update });
  const targets = targetsFor(row, config);
  const changeType = (type: ChangeType) => {
    const next = { ...row, type };
    const options = targetsFor(next, config);
    patch({ type, target: options.includes(row.target) ? row.target : options[0] ?? "" });
  };
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2" data-event-row={index}>
      <span className="w-6 text-sm text-muted-foreground">{index + 1}.</span>
      <Choice
        label={`Event ${index + 1} trigger`}
        value={row.trigger}
        options={[
          { value: "step", label: "after step" },
          { value: "sim_time", label: "at sim time" },
        ]}
        onChange={(trigger) => patch({ trigger })}
        width="w-32"
      />
      {row.trigger === "step" ? (
        <Input
          type="number"
          min={1}
          className="w-24"
          aria-label={`Event ${index + 1} step`}
          value={row.step}
          onChange={(event) => patch({ step: Math.floor(Number(event.target.value)) })}
        />
      ) : (
        <Input
          className="w-56"
          placeholder="2026-01-01T12:00:00Z"
          aria-label={`Event ${index + 1} sim time`}
          value={row.simTime}
          onChange={(event) => patch({ simTime: event.target.value })}
        />
      )}
      <Choice
        label={`Event ${index + 1} change`}
        value={row.type}
        options={(Object.keys(CHANGE_LABELS) as ChangeType[]).map((type) => ({ value: type, label: CHANGE_LABELS[type] }))}
        onChange={changeType}
      />
      {row.type === "comm_loss" && (
        <Choice<CommTarget>
          label={`Event ${index + 1} comm target`}
          value={row.commTarget}
          options={["asset", "meter", "poi_meter"]}
          onChange={(commTarget) => {
            const options = targetsFor({ ...row, commTarget }, config);
            patch({ commTarget, target: options[0] ?? "" });
          }}
          width="w-32"
        />
      )}
      {targets.length > 0 && (
        <Choice label={`Event ${index + 1} target`} value={row.target} options={targets} onChange={(target) => patch({ target })} width="w-32" />
      )}
      {row.type === "breaker" && (
        <Choice
          label={`Event ${index + 1} position`}
          value={row.closed ? "close" : "open"}
          options={["open", "close"]}
          onChange={(position) => patch({ closed: position === "close" })}
          width="w-24"
        />
      )}
      {row.type === "asset_fault" && row.active && (
        <Choice<FaultCause>
          label={`Event ${index + 1} cause`}
          value={row.cause}
          options={causesFor(row.target, config, catalog).map((info) => ({
            value: info.cause,
            label: `${info.label} (${info.severity})`,
          }))}
          onChange={(cause) => patch({ cause })}
          width="w-56"
        />
      )}
      {row.type === "asset_fault" && row.active && (
        <div className="flex items-center gap-1" title="A fault clears itself 2-10 min of sim time later, without latching">
          <Switch
            checked={row.autoRestore}
            onCheckedChange={(autoRestore) => patch({ autoRestore })}
            aria-label={`Event ${index + 1} auto-restore`}
          />
          <span className="text-xs text-muted-foreground">auto-restore</span>
        </div>
      )}
      {(row.type === "asset_fault" || row.type === "comm_loss") && (
        <div className="flex items-center gap-1">
          <Switch checked={row.active} onCheckedChange={(active) => patch({ active })} aria-label={`Event ${index + 1} active`} />
          <span className="text-xs text-muted-foreground">{row.active ? "start" : row.type === "asset_fault" ? "clear (faults latch)" : "clear"}</span>
        </div>
      )}
      {(row.type === "grid_voltage" || row.type === "grid_frequency") && (
        <Input
          type="number"
          step={0.01}
          className="w-28"
          placeholder="empty = restore"
          aria-label={`Event ${index + 1} value`}
          value={row.value}
          onChange={(event) => patch({ value: event.target.value })}
        />
      )}
      <Input
        className="w-40"
        placeholder="label (optional)"
        aria-label={`Event ${index + 1} label`}
        value={row.label}
        onChange={(event) => patch({ label: event.target.value })}
      />
      <Button size="icon" variant="ghost" aria-label={`Remove event ${index + 1}`} onClick={onRemove}>
        <Trash2 className="w-4 h-4" />
      </Button>
    </div>
  );
}

function ExpectedRowFields({
  row,
  index,
  onChange,
  onRemove,
}: {
  row: ExpectedRow;
  index: number;
  onChange: (row: ExpectedRow) => void;
  onRemove: () => void;
}) {
  const patch = (update: Partial<ExpectedRow>) => onChange({ ...row, ...update });
  const field = (key: keyof ExpectedRow, placeholder: string, width: string) => (
    <Input
      className={width}
      placeholder={placeholder}
      aria-label={`Expected point ${index + 1} ${placeholder}`}
      value={row[key]}
      onChange={(event) => patch({ [key]: event.target.value })}
    />
  );
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2" data-expected-row={index}>
      <span className="w-6 text-sm text-muted-foreground">{index + 1}.</span>
      <Input
        className="w-40"
        list="scenario-devices"
        placeholder="device"
        aria-label={`Expected point ${index + 1} device`}
        value={row.device}
        onChange={(event) => patch({ device: event.target.value })}
      />
      {field("point", "point", "w-24")}
      {field("equals", "equals", "w-28")}
      {field("tolerance", "±", "w-16")}
      {field("bitsSet", "bits set", "w-40")}
      {field("bitsClear", "bits clear", "w-40")}
      {field("fromStep", "from step", "w-20")}
      {field("toStep", "to step", "w-20")}
      {field("note", "note", "w-40")}
      <Button size="icon" variant="ghost" aria-label={`Remove expected point ${index + 1}`} onClick={onRemove}>
        <Trash2 className="w-4 h-4" />
      </Button>
    </div>
  );
}

// Create or edit a stored event scenario of a site: what it does, its timed condition changes,
// and the points it impacts with their expected values.
export function EventScenarioEditor({ siteName, config, editing, copyOf, open, onClose }: Props) {
  const refresh = useRefreshPowerflow();
  const source = editing ?? copyOf;
  const [name, setName] = useState(editing?.name ?? (copyOf ? `${copyOf.name}-copy` : ""));
  const [description, setDescription] = useState(source?.scenario.description ?? "");
  const [rows, setRows] = useState<EventRow[]>(() => source?.scenario.events.map(rowFromEvent) ?? [blankRow()]);
  const [expectedRows, setExpectedRows] = useState<ExpectedRow[]>(
    () => source?.scenario.expected_points?.map(expectedRowFrom) ?? [],
  );
  const [saveError, setSaveError] = useState<string | null>(null);
  const catalog = useFaultCauses().data ?? [];

  const problems = [
    ...(NAME_PATTERN.test(name) ? [] : ["Name: lowercase letters, digits, - and _ only."]),
    ...rowProblems(rows, config, catalog),
    ...expectedRowProblems(expectedRows),
  ];
  const save = useMutation({
    mutationFn: () => powerflowApi.saveEventScenario(siteName, name, scenarioFromRows(description, rows, expectedRows)),
    onSuccess: () => {
      refresh();
      toast({ title: `Saved scenario ${name}` });
      onClose();
    },
    onError: (error) => setSaveError(getErrorMessage(error, "Saving the scenario failed")),
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-5xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editing ? `Edit ${editing.name}` : copyOf ? `Duplicate ${copyOf.name}` : "New event scenario"}</DialogTitle>
          <DialogDescription>
            Events fire before the given step after the scenario starts, or at a sim time. Several on the same step fire in
            order. A cleared fault stays latched until an alarm reset event, unless it was started with auto-restore.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label htmlFor="scenario_name">Name</Label>
            <Input id="scenario_name" value={name} disabled={editing !== null} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor="scenario_description">What the scenario does</Label>
            <Textarea id="scenario_description" rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
          </div>
        </div>
        <h3 className="font-semibold text-foreground">Events</h3>
        <div className="space-y-2">
          {rows.map((row, index) => (
            <EventRowFields
              key={index}
              row={row}
              index={index}
              config={config}
              catalog={catalog}
              onChange={(next) => setRows((current) => current.map((item, position) => (position === index ? next : item)))}
              onRemove={() => setRows((current) => current.filter((_item, position) => position !== index))}
            />
          ))}
          <Button
            size="sm"
            variant="outline"
            className="gap-1"
            onClick={() => setRows((current) => [...current, blankRow((current.at(-1)?.step ?? 0) + 10)])}
          >
            <Plus className="w-4 h-4" /> Add event
          </Button>
        </div>
        <h3 className="font-semibold text-foreground">Impacted points and expected values</h3>
        <p className="text-xs text-muted-foreground">
          Point-standard device and point (as on Modbus), and what it should read from step to step (counted like the events).
          Equals takes a number (SI units) or an enum value (e.g. FAULT); bits are labels, comma-separated (e.g. OVER_TEMP).
        </p>
        <datalist id="scenario-devices">
          {deviceLabels(config).map((label) => (
            <option key={label} value={label} />
          ))}
        </datalist>
        <div className="space-y-2">
          {expectedRows.map((row, index) => (
            <ExpectedRowFields
              key={index}
              row={row}
              index={index}
              onChange={(next) => setExpectedRows((current) => current.map((item, position) => (position === index ? next : item)))}
              onRemove={() => setExpectedRows((current) => current.filter((_item, position) => position !== index))}
            />
          ))}
          <Button size="sm" variant="outline" className="gap-1" onClick={() => setExpectedRows((current) => [...current, blankExpectedRow()])}>
            <Plus className="w-4 h-4" /> Add expected point
          </Button>
        </div>
        {problems.length > 0 && (
          <ul className="text-sm text-destructive list-disc pl-5" role="alert">
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        )}
        {saveError && (
          <p role="alert" className="text-sm text-destructive">
            {saveError}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={problems.length > 0 || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
