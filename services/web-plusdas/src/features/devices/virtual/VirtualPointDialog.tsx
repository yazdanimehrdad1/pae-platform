import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { devicesApi } from "@/api/devices";
import { getErrorMessage } from "@/api/client";
import type { DevicePoint, VirtualCalculationFunction } from "@/api/types/devicePoints";
import { ConditionGroup } from "@/shared/components/conditions/ConditionGroup";
import { PointCombobox } from "@/shared/components/conditions/PointCombobox";
import { toast } from "@/shared/hooks/use-toast";
import { devicePointOptions } from "@/shared/components/conditions/devicePointOptions";
import {
  CALCULATION_FUNCTION_LABELS,
  MAX_CASES,
  MAX_INPUTS,
  describeDraft,
  draftFromPoint,
  emptyDraft,
  isTwoInputFunction,
  newCase,
  newInput,
  toDefinition,
  validateDraft,
  type CaseDraft,
  type VirtualKind,
  type VirtualPointDraft,
} from "./lib/virtualDefinition";

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <p id={id} role="alert" className="text-xs text-alarm-fault">{message}</p> : null;
}

/** Create a virtual point on a device, or edit one (`point`). Inputs can be any point on the site. */
export function VirtualPointDialog({ open, onOpenChange, siteId, deviceId, point }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  deviceId: number;
  point?: DevicePoint | null;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<VirtualPointDraft>(emptyDraft);
  const [hasTriedSave, setHasTriedSave] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDraft(point ? draftFromPoint(point) : emptyDraft());
    setHasTriedSave(false);
  }, [open, point]);

  const { data: siteDevices = [] } = useQuery({
    queryKey: ["site-devices-with-points", siteId],
    queryFn: () => devicesApi.getBySiteWithPoints(siteId),
    enabled: open && !!siteId,
  });
  const pointOptions = useMemo(() => devicePointOptions(siteDevices), [siteDevices]);
  const pointsById = useMemo(() => new Map(pointOptions.map(option => [option.id, option])), [pointOptions]);

  const { errors, isValid } = validateDraft(draft);
  const shownErrors = hasTriedSave ? errors : { caseOutputs: {}, inputs: {}, conditions: {} };
  const update = (patch: Partial<VirtualPointDraft>) => setDraft(previous => ({ ...previous, ...patch }));
  const updateCase = (key: string, patch: Partial<CaseDraft>) =>
    update({ cases: draft.cases.map(entry => (entry.key === key ? { ...entry, ...patch } : entry)) });

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = { name: draft.name.trim(), unit: draft.unit.trim() || null, definition: toDefinition(draft) };
      return point
        ? devicesApi.updateVirtualPoint(siteId, deviceId, point.id, payload)
        : devicesApi.createVirtualPoint(siteId, deviceId, payload);
    },
    onSuccess: saved => {
      queryClient.invalidateQueries({ queryKey: ["device-points", siteId, deviceId] });
      queryClient.invalidateQueries({ queryKey: ["device-record", siteId, deviceId] });
      queryClient.invalidateQueries({ queryKey: ["site-devices-with-points", siteId] });
      toast({ title: point ? "Virtual point updated" : "Virtual point created", description: saved.name });
      onOpenChange(false);
    },
    onError: error => toast({ title: "Failed to save virtual point", description: getErrorMessage(error), variant: "destructive" }),
  });

  const handleSave = () => {
    setHasTriedSave(true);
    if (isValid) saveMutation.mutate();
  };

  const setCalcFunction = (calcFunction: VirtualCalculationFunction) => {
    const inputs = isTwoInputFunction(calcFunction)
      ? [draft.inputs[0] ?? newInput(), draft.inputs[1] ?? newInput()]
      : draft.inputs;
    update({ calcFunction, inputs });
  };

  const twoInputs = isTwoInputFunction(draft.calcFunction);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{point ? `Edit virtual point "${point.name}"` : "New virtual point"}</DialogTitle>
          <DialogDescription>
            Computed by the backend from the stored readings of other points on this site, each time it is read. It trends like any other point.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="space-y-1 md:col-span-2">
              <Label htmlFor="virtual-name">Name</Label>
              <Input id="virtual-name" value={draft.name} maxLength={255} autoComplete="off" onChange={event => update({ name: event.target.value })}
                aria-invalid={!!shownErrors.name} aria-describedby="virtual-name-error" />
              <FieldError id="virtual-name-error" message={shownErrors.name} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="virtual-unit">Unit</Label>
              <Input id="virtual-unit" value={draft.unit} maxLength={50} placeholder="optional" onChange={event => update({ unit: event.target.value })} />
            </div>
          </div>

          <RadioGroup value={draft.kind} onValueChange={kind => update({ kind: kind as VirtualKind })} className="flex gap-6">
            <div className="flex items-center gap-2">
              <RadioGroupItem value="condition" id="virtual-kind-condition" />
              <Label htmlFor="virtual-kind-condition" className="font-normal">Condition (states from rules)</Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="calculation" id="virtual-kind-calculation" />
              <Label htmlFor="virtual-kind-calculation" className="font-normal">Calculation (from other values)</Label>
            </div>
          </RadioGroup>

          {draft.kind === "condition" ? (
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">Cases are checked in order; the first that matches sets the output.</p>
              {draft.cases.map((entry, index) => (
                <div key={entry.key} className="space-y-2 rounded-md border border-border p-3" data-testid="virtual-case">
                  <div className="flex flex-wrap items-end gap-3">
                    <span className="pb-2 text-sm font-medium">{index === 0 ? "If" : "Else if"}</span>
                    <div className="space-y-1">
                      <Label htmlFor={`${entry.key}-output`} className="text-xs">Output</Label>
                      <Input id={`${entry.key}-output`} className="w-24" inputMode="numeric" value={entry.output}
                        onChange={event => updateCase(entry.key, { output: event.target.value })}
                        aria-invalid={!!shownErrors.caseOutputs[entry.key]} aria-describedby={`${entry.key}-output-error`} />
                    </div>
                    <div className="min-w-[10rem] flex-1 space-y-1">
                      <Label htmlFor={`${entry.key}-label`} className="text-xs">State name</Label>
                      <Input id={`${entry.key}-label`} value={entry.label} maxLength={64} placeholder="e.g. ready"
                        onChange={event => updateCase(entry.key, { label: event.target.value })} />
                    </div>
                    {draft.cases.length > 1 && (
                      <Button variant="ghost" size="icon" aria-label={`Remove case ${index + 1}`}
                        onClick={() => update({ cases: draft.cases.filter(other => other.key !== entry.key) })}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                  <FieldError id={`${entry.key}-output-error`} message={shownErrors.caseOutputs[entry.key]} />
                  <ConditionGroup
                    group={entry.group}
                    onChange={group => updateCase(entry.key, { group })}
                    points={pointOptions}
                    errorsFor={key => shownErrors.conditions[key]}
                    label={`Case ${index + 1}`}
                  />
                </div>
              ))}
              {draft.cases.length < MAX_CASES && (
                <Button variant="outline" size="sm" className="gap-1"
                  onClick={() => update({ cases: [...draft.cases, newCase(Math.max(0, ...draft.cases.map(entry => Number(entry.output) || 0)) + 1)] })}>
                  <Plus className="h-3 w-3" />Case
                </Button>
              )}
              <div className="flex flex-wrap items-end gap-3 rounded-md border border-dashed border-border p-3">
                <span className="pb-2 text-sm font-medium">Otherwise</span>
                <div className="space-y-1">
                  <Label htmlFor="virtual-default-output" className="text-xs">Output</Label>
                  <Input id="virtual-default-output" className="w-24" inputMode="numeric" value={draft.defaultOutput}
                    onChange={event => update({ defaultOutput: event.target.value })}
                    aria-invalid={!!shownErrors.defaultOutput} aria-describedby="virtual-default-output-error" />
                </div>
                <div className="min-w-[10rem] flex-1 space-y-1">
                  <Label htmlFor="virtual-default-label" className="text-xs">State name</Label>
                  <Input id="virtual-default-label" value={draft.defaultLabel} maxLength={64} placeholder="e.g. not ready"
                    onChange={event => update({ defaultLabel: event.target.value })} />
                </div>
                <FieldError id="virtual-default-output-error" message={shownErrors.defaultOutput} />
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1 md:w-64">
                <Label htmlFor="virtual-function">Function</Label>
                <Select value={draft.calcFunction} onValueChange={value => setCalcFunction(value as VirtualCalculationFunction)}>
                  <SelectTrigger id="virtual-function"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {(Object.keys(CALCULATION_FUNCTION_LABELS) as VirtualCalculationFunction[]).map(fn => (
                      <SelectItem key={fn} value={fn}>{CALCULATION_FUNCTION_LABELS[fn]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Inputs</Label>
                {draft.inputs.map((input, index) => (
                  <div key={input.key} className="flex items-start gap-2" data-testid="virtual-input">
                    <span className="w-6 pt-2 text-sm text-muted-foreground">{twoInputs ? (index === 0 ? "A" : "B") : index + 1}</span>
                    <div className="min-w-0 flex-1 space-y-1">
                      <PointCombobox options={pointOptions} value={input.pointId} ariaLabel={`Input ${index + 1}`}
                        onChange={pointId => update({ inputs: draft.inputs.map(other => (other.key === input.key ? { ...other, pointId } : other)) })}
                        invalid={!!shownErrors.inputs[input.key]} describedBy={`${input.key}-error`} />
                      <FieldError id={`${input.key}-error`} message={shownErrors.inputs[input.key]} />
                    </div>
                    {!twoInputs && draft.inputs.length > 1 && (
                      <Button variant="ghost" size="icon" aria-label={`Remove input ${index + 1}`}
                        onClick={() => update({ inputs: draft.inputs.filter(other => other.key !== input.key) })}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
                {!twoInputs && draft.inputs.length < MAX_INPUTS && (
                  <Button variant="outline" size="sm" className="gap-1" onClick={() => update({ inputs: [...draft.inputs, newInput()] })}>
                    <Plus className="h-3 w-3" />Input
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3 md:w-80">
                <div className="space-y-1">
                  <Label htmlFor="virtual-scale">Scale (×)</Label>
                  <Input id="virtual-scale" inputMode="decimal" value={draft.scale} onChange={event => update({ scale: event.target.value })}
                    aria-invalid={!!shownErrors.scale} aria-describedby="virtual-scale-error" />
                  <FieldError id="virtual-scale-error" message={shownErrors.scale} />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="virtual-offset">Offset (+)</Label>
                  <Input id="virtual-offset" inputMode="decimal" value={draft.offset} onChange={event => update({ offset: event.target.value })}
                    aria-invalid={!!shownErrors.offset} aria-describedby="virtual-offset-error" />
                  <FieldError id="virtual-offset-error" message={shownErrors.offset} />
                </div>
              </div>
            </div>
          )}

          <div className="rounded-md bg-muted/50 p-3 text-xs" aria-label="Summary">
            <p className="mb-1 font-medium text-muted-foreground">Summary</p>
            {describeDraft(draft, pointsById).map((line, index) => <p key={index} className="font-mono">{line}</p>)}
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? "Saving..." : point ? "Save changes" : "Create virtual point"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
