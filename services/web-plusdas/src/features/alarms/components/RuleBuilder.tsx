import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { devicesApi, sitesApi } from "@/api";
import { ConditionRow } from "@/shared/components/conditions/ConditionRow";
import { newCondition, type ComparisonOperator, type ConditionDraft } from "@/shared/components/conditions/conditionModel";
import { devicePointOptions } from "@/shared/components/conditions/devicePointOptions";
import { describeCondition } from "../lib/alarmModel";
import { ALARM_OPERATORS, toAlarmOperator } from "../lib/conditionPoints";
import { RULE_NAME_HINT, RULE_NAME_MAX_LENGTH, validateRuleName } from "../lib/ruleName";
import type { Device, NotificationSettings, Rule, RuleTarget, Severity } from "../types";
import { NotificationToggles } from "./NotificationToggles";
const DELAY_PRESETS = [
  { value: "0", label: "0 s" },
  { value: "30", label: "30 s" },
  { value: "300", label: "5 min" },
  { value: "900", label: "15 min" },
  { value: "custom", label: "Custom" },
];

type RuleType = Rule["type"];
type Errors = Partial<Record<"name" | "point" | "device" | "threshold" | "delay" | "deadband" | "staleAfter", string>>;

/** Parses a required number: returns the value, or the error text to show beside the field. */
function parseNumber(raw: string, { min }: { min?: number } = {}): number | string {
  if (raw.trim() === "") return "Required";
  const value = Number(raw);
  if (!Number.isFinite(value)) return "Must be a number";
  if (min !== undefined && value < min) return `Must be ${min} or more`;
  return value;
}

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <p id={id} role="alert" className="text-xs text-alarm-fault">{message}</p> : null;
}

/**
 * Inline form for a new alarm rule: a threshold on a real device point of a site (backend-ot), or a
 * comms-stale check on a device. Rules on device points are saved and listed; they raise alarms once
 * backend-ot evaluates rules (until then the page's alarms come from the demo data).
 */
export function RuleBuilder({ devices, existingNames, onSave, onCancel }: {
  /** Devices for the comms-stale rule (the page's demo devices). */
  devices: Device[];
  /** Names of the existing rules; a new name must differ from all of them, ignoring case. */
  existingNames: string[];
  onSave: (rule: Rule) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [hasTriedSave, setHasTriedSave] = useState(false);
  const [type, setType] = useState<RuleType>("threshold");
  const [deviceId, setDeviceId] = useState<string>("");
  const [delayPreset, setDelayPreset] = useState("0");
  const [customDelay, setCustomDelay] = useState("");
  const [deadband, setDeadband] = useState("0");
  const [staleAfter, setStaleAfter] = useState("60");
  const [severity, setSeverity] = useState<Severity>("warning");
  const [message, setMessage] = useState("");
  const [notify, setNotify] = useState<NotificationSettings>({ mobile: true, email: false });
  const [errors, setErrors] = useState<Errors>({});
  const [isSaving, setIsSaving] = useState(false);

  const devicesById = useMemo(() => new Map(devices.map(device => [device.id, device])), [devices]);

  // The threshold's point: a real device point of the chosen site, from backend-ot.
  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: sitesApi.getAll });
  const [siteId, setSiteId] = useState("");
  useEffect(() => {
    if (!siteId && sites.length > 0) setSiteId(sites[0].id);
  }, [sites, siteId]);
  const { data: siteDevices = [], isLoading: arePointsLoading } = useQuery({
    queryKey: ["site-devices-with-points", siteId],
    queryFn: () => devicesApi.getBySiteWithPoints(siteId),
    enabled: !!siteId,
  });
  const pointOptions = useMemo(() => devicePointOptions(siteDevices, { includeVirtual: true }), [siteDevices]);
  // The threshold condition, edited with the shared condition row (value operand only).
  const [condition, setCondition] = useState<ConditionDraft>(newCondition);
  const selectedPoint = pointOptions.find(option => option.id === condition.pointId) ?? null;
  const changeSite = (nextSiteId: string) => {
    setSiteId(nextSiteId);
    setCondition(newCondition());
  };

  const handleSave = async () => {
    setHasTriedSave(true);
    const nextErrors: Errors = {};
    const nameError = validateRuleName(name, existingNames);
    if (nameError) nextErrors.name = nameError;
    let rule: Rule | null = null;
    const id = `rule-${Date.now()}`;

    if (type === "threshold") {
      if (!selectedPoint) nextErrors.point = "Choose a point";
      const thresholdValue = parseNumber(condition.value);
      if (typeof thresholdValue === "string") nextErrors.threshold = thresholdValue;
      const delayValue = delayPreset === "custom" ? parseNumber(customDelay, { min: 0 }) : Number(delayPreset);
      if (typeof delayValue === "string") nextErrors.delay = delayValue;
      const deadbandValue = parseNumber(deadband, { min: 0 });
      if (typeof deadbandValue === "string") nextErrors.deadband = deadbandValue;
      if (Object.keys(nextErrors).length === 0 && selectedPoint) {
        const target: RuleTarget = {
          siteId,
          deviceName: selectedPoint.group,
          pointName: selectedPoint.name,
          unit: selectedPoint.unit ?? null,
          ...(selectedPoint.states ? { states: Object.fromEntries(selectedPoint.states.map(state => [state.value, state.label])) } : {}),
        };
        const draft = {
          id, type: "threshold" as const, name, pointId: selectedPoint.id, target,
          operator: toAlarmOperator(condition.operator as ComparisonOperator),
          threshold: thresholdValue as number, delaySec: delayValue as number, deadband: deadbandValue as number,
          severity, message: "", enabled: true, notify,
        };
        const conditionText = describeCondition(draft, null);
        rule = { ...draft, name, message: message.trim() || `${target.deviceName}: ${conditionText}` };
      }
    } else {
      if (!deviceId) nextErrors.device = "Choose a device";
      const staleValue = parseNumber(staleAfter, { min: 1 });
      if (typeof staleValue === "string") nextErrors.staleAfter = staleValue;
      if (Object.keys(nextErrors).length === 0) {
        const deviceName = devicesById.get(deviceId)?.name ?? deviceId;
        rule = {
          id, type: "comms_stale", name, deviceId, staleAfterSec: staleValue as number,
          severity, message: message.trim() || `${deviceName}: no successful poll for over ${staleValue} s`, enabled: true, notify,
        };
      }
    }

    setErrors(nextErrors);
    if (!rule) return;
    setIsSaving(true);
    try {
      await onSave(rule);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section aria-labelledby="rule-builder-heading" className="space-y-4 rounded-md border border-border bg-card p-4">
      <h2 id="rule-builder-heading" className="text-sm font-semibold">New rule</h2>

      <div className="max-w-xl space-y-1">
        <div className="flex items-baseline justify-between gap-2">
          <Label htmlFor="rule-name">Name</Label>
          <span className="text-xs tabular-nums text-muted-foreground" aria-live="polite">
            {name.length} / {RULE_NAME_MAX_LENGTH}
          </span>
        </div>
        <Input
          id="rule-name"
          value={name}
          maxLength={RULE_NAME_MAX_LENGTH}
          placeholder="e.g. t1_top_oil_temp_high"
          spellCheck={false}
          autoComplete="off"
          className="font-mono"
          onChange={e => {
            setName(e.target.value);
            if (hasTriedSave) setErrors(prev => ({ ...prev, name: validateRuleName(e.target.value, existingNames) ?? undefined }));
          }}
          aria-invalid={!!errors.name}
          aria-describedby="rule-name-hint rule-name-error"
        />
        <p id="rule-name-hint" className="text-xs text-muted-foreground">{RULE_NAME_HINT}</p>
        <FieldError id="rule-name-error" message={errors.name} />
      </div>

      <RadioGroup value={type} onValueChange={value => { setType(value as RuleType); setErrors(prev => ({ name: prev.name })); }} className="flex gap-6">
        <div className="flex items-center gap-2">
          <RadioGroupItem value="threshold" id="rule-type-threshold" />
          <Label htmlFor="rule-type-threshold" className="font-normal">Threshold on a point</Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="comms_stale" id="rule-type-stale" />
          <Label htmlFor="rule-type-stale" className="font-normal">Comms stale</Label>
        </div>
      </RadioGroup>

      {type === "threshold" ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor="rule-site">Site</Label>
            <Select value={siteId} onValueChange={changeSite}>
              <SelectTrigger id="rule-site"><SelectValue placeholder="Choose a site" /></SelectTrigger>
              <SelectContent>{sites.map(site => <SelectItem key={site.id} value={site.id}>{site.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <p className="self-end pb-2 text-xs text-muted-foreground md:col-span-4">
            {arePointsLoading ? "Loading the site's points…" : "Points of this site's devices. Rules on them raise alarms once alarms run in backend-ot; this page's alarms are demo data until then."}
          </p>
          <ConditionRow
            className="md:col-span-6"
            condition={condition}
            onChange={setCondition}
            points={pointOptions}
            operators={ALARM_OPERATORS}
            showLabels
            labels={{ point: "Point", operator: "Operator", value: "Threshold" }}
            ids={{ point: "rule-point", operator: "rule-operator", value: "rule-threshold" }}
            errors={{ point: errors.point, value: errors.threshold }}
          />
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor="rule-delay">Delay (for)</Label>
            <div className="flex gap-2">
              <Select value={delayPreset} onValueChange={setDelayPreset}>
                <SelectTrigger id="rule-delay"><SelectValue /></SelectTrigger>
                <SelectContent>{DELAY_PRESETS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
              </Select>
              {delayPreset === "custom" && (
                <Input aria-label="Custom delay in seconds" placeholder="seconds" inputMode="numeric" value={customDelay}
                  onChange={e => setCustomDelay(e.target.value)} aria-invalid={!!errors.delay} aria-describedby="rule-delay-error" />
              )}
            </div>
            <FieldError id="rule-delay-error" message={errors.delay} />
          </div>
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor="rule-deadband">Deadband (clear hysteresis)</Label>
            <Input id="rule-deadband" inputMode="decimal" value={deadband} onChange={e => setDeadband(e.target.value)}
              aria-invalid={!!errors.deadband} aria-describedby="rule-deadband-error" />
            <FieldError id="rule-deadband-error" message={errors.deadband} />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
          <div className="space-y-1 md:col-span-3">
            <Label htmlFor="rule-device">Device</Label>
            <Select value={deviceId} onValueChange={setDeviceId}>
              <SelectTrigger id="rule-device" aria-invalid={!!errors.device} aria-describedby="rule-device-error">
                <SelectValue placeholder="Choose a device" />
              </SelectTrigger>
              <SelectContent>{devices.map(device => <SelectItem key={device.id} value={device.id}>{device.name}</SelectItem>)}</SelectContent>
            </Select>
            <FieldError id="rule-device-error" message={errors.device} />
          </div>
          <div className="space-y-1 md:col-span-2">
            <Label htmlFor="rule-stale-after">No successful poll for more than (s)</Label>
            <Input id="rule-stale-after" inputMode="numeric" value={staleAfter} onChange={e => setStaleAfter(e.target.value)}
              aria-invalid={!!errors.staleAfter} aria-describedby="rule-stale-after-error" />
            <FieldError id="rule-stale-after-error" message={errors.staleAfter} />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
        <div className="space-y-1 md:col-span-2">
          <Label>Severity</Label>
          <RadioGroup value={severity} onValueChange={value => setSeverity(value as Severity)} className="flex h-10 items-center gap-6">
            <div className="flex items-center gap-2">
              <RadioGroupItem value="warning" id="rule-severity-warning" />
              <Label htmlFor="rule-severity-warning" className="font-normal">Warning</Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="fault" id="rule-severity-fault" />
              <Label htmlFor="rule-severity-fault" className="font-normal">Fault</Label>
            </div>
          </RadioGroup>
        </div>
        <div className="space-y-1 md:col-span-4">
          <Label htmlFor="rule-message">Message</Label>
          <Input id="rule-message" placeholder="Shown in the alarm list and event log (defaults to the condition)"
            value={message} onChange={e => setMessage(e.target.value)} />
        </div>
      </div>

      <div className="space-y-1">
        <Label>Notifications</Label>
        <div className="flex flex-wrap items-center gap-3">
          <NotificationToggles value={notify} onChange={setNotify} label="Notifications for this rule" />
          <span className="text-xs text-muted-foreground">
            Sent when the rule raises an alarm, on each selected channel. Select none to only show it here.
          </span>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button onClick={handleSave} disabled={isSaving}>{isSaving ? "Saving..." : "Save rule"}</Button>
      </div>
    </section>
  );
}
