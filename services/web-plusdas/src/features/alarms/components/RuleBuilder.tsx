import { useMemo, useState } from "react";
import type { AlarmDefinitionCreateRequest, AlarmRuleInput } from "@/api/types/alarms";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ConditionGroup } from "@/shared/components/conditions/ConditionGroup";
import { ConditionRow } from "@/shared/components/conditions/ConditionRow";
import {
  describeConditionDraft,
  describeGroupDraft,
  isBitOperator,
  newCondition,
  newGroup,
  validateCondition,
  type ConditionDraft,
  type ConditionErrors,
  type ConditionGroupDraft,
} from "@/shared/components/conditions/conditionModel";
import { conditionFromWire, conditionToWire, groupFromWire, groupToWire } from "@/shared/components/conditions/conditionWire";
import { RULE_NAME_HINT, RULE_NAME_MAX_LENGTH, validateRuleName } from "../lib/ruleName";
import type { Device, NotificationSettings, Point, Rule, Severity } from "../types";
import { NotificationToggles } from "./NotificationToggles";

const DELAY_PRESETS = [
  { value: "0", label: "0 s" },
  { value: "30", label: "30 s" },
  { value: "300", label: "5 min" },
  { value: "900", label: "15 min" },
  { value: "custom", label: "Custom" },
];

type RuleKind = AlarmRuleInput["kind"];
type Errors = Partial<Record<"name" | "device" | "delay" | "deadband" | "staleAfter", string>>;

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

/** The form's starting values: empty for a new rule, the rule's own for an edit. */
function initialForm(rule: Rule | undefined) {
  const spec = rule?.rule ?? null;
  const delay = spec && spec.kind !== "comms_stale" ? spec.delay_sec : 0;
  const isPreset = DELAY_PRESETS.some(preset => preset.value === String(delay));
  return {
    kind: (spec?.kind ?? "threshold") as RuleKind,
    condition: spec?.kind === "threshold" ? conditionFromWire(spec.condition) : newCondition(),
    group: spec?.kind === "condition" ? groupFromWire(spec.when) : newGroup("all"),
    deviceId: spec?.kind === "comms_stale" ? String(spec.device_id) : "",
    delayPreset: isPreset ? String(delay) : "custom",
    customDelay: isPreset ? "" : String(delay),
    deadband: spec?.kind === "threshold" ? String(spec.deadband) : "0",
    staleAfter: spec?.kind === "comms_stale" ? String(spec.stale_after_sec) : "60",
  };
}

function collectGroupErrors(group: ConditionGroupDraft, into: Record<string, ConditionErrors>): void {
  for (const item of group.items) {
    if (item.type === "group") { collectGroupErrors(item.group, into); continue; }
    const errors = validateCondition(item.condition);
    if (Object.keys(errors).length > 0) into[item.key] = errors;
  }
}

/**
 * Inline form for a new user alarm rule on the page's site, or for editing one (`initial`), saved to backend-ot (which evaluates it):
 * - a threshold: one point against a value or another point, or a bit test; with delay and deadband;
 * - a condition: ALL/ANY groups over several points (the virtual point editor), with a delay;
 * - comms stale: a device with no successful poll for a while.
 */
export function RuleBuilder({ initial, points, devices, existingNames, canEnable, onSave, onCancel }: {
  /** The user rule to edit; omitted for a new rule. */
  initial?: Rule;
  /** The site's device points (standardized, virtual and native). */
  points: Point[];
  devices: Device[];
  /** Names of the site's alarms; the name must differ from all of them (but the edited rule's own), ignoring case. */
  existingNames: string[];
  /** False when the site already has the maximum number of enabled rules (an edited enabled rule keeps its place). */
  canEnable: boolean;
  onSave: (request: AlarmDefinitionCreateRequest) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [form] = useState(() => initialForm(initial));
  const isEdit = initial !== undefined;
  const [name, setName] = useState(initial?.name ?? "");
  const [hasTriedSave, setHasTriedSave] = useState(false);
  const [kind, setKind] = useState<RuleKind>(form.kind);
  const [condition, setCondition] = useState<ConditionDraft>(form.condition);
  const [group, setGroup] = useState<ConditionGroupDraft>(form.group);
  const [deviceId, setDeviceId] = useState(form.deviceId);
  const [delayPreset, setDelayPreset] = useState(form.delayPreset);
  const [customDelay, setCustomDelay] = useState(form.customDelay);
  const [deadband, setDeadband] = useState(form.deadband);
  const [staleAfter, setStaleAfter] = useState(form.staleAfter);
  const [severity, setSeverity] = useState<Severity>(initial?.severity ?? "warning");
  const [message, setMessage] = useState(initial?.message ?? "");
  const [notify, setNotify] = useState<NotificationSettings>(initial?.notify ?? { mobile: true, email: false });
  const canEnableThis = canEnable || !!initial?.enabled;
  const [enabled, setEnabled] = useState(isEdit ? initial.enabled : canEnable);
  // The edited rule's own name is not taken.
  const takenNames = useMemo(
    () => existingNames.filter(existing => existing.toLowerCase() !== initial?.name.toLowerCase()),
    [existingNames, initial],
  );
  const [errors, setErrors] = useState<Errors>({});
  const [conditionErrors, setConditionErrors] = useState<ConditionErrors>({});
  const [groupErrors, setGroupErrors] = useState<Record<string, ConditionErrors>>({});
  const [isSaving, setIsSaving] = useState(false);

  const pointsById = useMemo(() => new Map(points.map(point => [point.id, point])), [points]);
  const isBitTest = isBitOperator(condition.operator);

  const handleSave = async () => {
    setHasTriedSave(true);
    const nextErrors: Errors = {};
    const nameError = validateRuleName(name, takenNames);
    if (nameError) nextErrors.name = nameError;
    const delayValue = delayPreset === "custom" ? parseNumber(customDelay, { min: 0 }) : Number(delayPreset);
    let nextConditionErrors: ConditionErrors = {};
    const nextGroupErrors: Record<string, ConditionErrors> = {};
    let rule: AlarmRuleInput | null = null;
    let defaultMessage = "";

    if (kind === "threshold") {
      nextConditionErrors = validateCondition(condition);
      if (typeof delayValue === "string") nextErrors.delay = delayValue;
      const deadbandValue = isBitTest ? 0 : parseNumber(deadband, { min: 0 });
      if (typeof deadbandValue === "string") nextErrors.deadband = deadbandValue;
      if (Object.keys(nextConditionErrors).length === 0 && typeof delayValue === "number" && typeof deadbandValue === "number") {
        rule = { kind: "threshold", condition: conditionToWire(condition), delay_sec: delayValue, deadband: deadbandValue };
        defaultMessage = describeConditionDraft(condition, pointsById);
      }
    } else if (kind === "condition") {
      collectGroupErrors(group, nextGroupErrors);
      if (typeof delayValue === "string") nextErrors.delay = delayValue;
      if (Object.keys(nextGroupErrors).length === 0 && typeof delayValue === "number") {
        rule = { kind: "condition", when: groupToWire(group), delay_sec: delayValue };
        defaultMessage = describeGroupDraft(group, pointsById);
      }
    } else {
      if (!deviceId) nextErrors.device = "Choose a device";
      const staleValue = parseNumber(staleAfter, { min: 1 });
      if (typeof staleValue === "string") nextErrors.staleAfter = staleValue;
      if (deviceId && typeof staleValue === "number") {
        rule = { kind: "comms_stale", device_id: Number(deviceId), stale_after_sec: staleValue };
        const deviceName = devices.find(device => device.id === deviceId)?.name ?? deviceId;
        defaultMessage = `${deviceName}: no successful poll for over ${staleValue} s`;
      }
    }

    setErrors(nextErrors);
    setConditionErrors(nextConditionErrors);
    setGroupErrors(nextGroupErrors);
    if (!rule || Object.keys(nextErrors).length > 0) return;
    setIsSaving(true);
    try {
      await onSave({
        name, severity, rule, enabled: enabled && canEnableThis,
        message: message.trim() || defaultMessage,
        notify_mobile: notify.mobile, notify_email: notify.email,
      });
    } finally {
      setIsSaving(false);
    }
  };

  const delayField = (
    <div className="space-y-1 md:col-span-2">
      <Label htmlFor="rule-delay">Delay (for)</Label>
      <div className="flex gap-2">
        <Select value={delayPreset} onValueChange={setDelayPreset}>
          <SelectTrigger id="rule-delay"><SelectValue /></SelectTrigger>
          <SelectContent>{DELAY_PRESETS.map(preset => <SelectItem key={preset.value} value={preset.value}>{preset.label}</SelectItem>)}</SelectContent>
        </Select>
        {delayPreset === "custom" && (
          <Input aria-label="Custom delay in seconds" placeholder="seconds" inputMode="numeric" value={customDelay}
            onChange={e => setCustomDelay(e.target.value)} aria-invalid={!!errors.delay} aria-describedby="rule-delay-error" />
        )}
      </div>
      <FieldError id="rule-delay-error" message={errors.delay} />
    </div>
  );

  return (
    <section aria-labelledby="rule-builder-heading" className="space-y-4 rounded-md border border-border bg-card p-4">
      <h2 id="rule-builder-heading" className="text-sm font-semibold">
        {isEdit ? <>Edit rule <span className="font-mono">{initial.name}</span></> : "New rule"}
      </h2>

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
          placeholder="e.g. bess_soc_low"
          spellCheck={false}
          autoComplete="off"
          className="font-mono"
          onChange={e => {
            setName(e.target.value);
            if (hasTriedSave) setErrors(prev => ({ ...prev, name: validateRuleName(e.target.value, takenNames) ?? undefined }));
          }}
          aria-invalid={!!errors.name}
          aria-describedby="rule-name-hint rule-name-error"
        />
        <p id="rule-name-hint" className="text-xs text-muted-foreground">{RULE_NAME_HINT}</p>
        <FieldError id="rule-name-error" message={errors.name} />
      </div>

      <RadioGroup value={kind} onValueChange={value => { setKind(value as RuleKind); setErrors(prev => ({ name: prev.name })); }}
        className="flex flex-wrap gap-6">
        <div className="flex items-center gap-2">
          <RadioGroupItem value="threshold" id="rule-kind-threshold" />
          <Label htmlFor="rule-kind-threshold" className="font-normal">Threshold on a point</Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="condition" id="rule-kind-condition" />
          <Label htmlFor="rule-kind-condition" className="font-normal">Condition on several points</Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="comms_stale" id="rule-kind-stale" />
          <Label htmlFor="rule-kind-stale" className="font-normal">Comms stale</Label>
        </div>
      </RadioGroup>

      {isEdit && (
        <p className="text-xs text-muted-foreground">
          Changing what the rule checks clears its active alarm and restarts its delay. Other changes keep an active alarm.
        </p>
      )}

      {kind === "threshold" && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
          <ConditionRow
            className="md:col-span-6"
            condition={condition}
            onChange={setCondition}
            points={points}
            allowComparePoint
            showLabels
            labels={{ point: "Point", operator: "Operator", value: "Threshold" }}
            ids={{ point: "rule-point", operator: "rule-operator", value: "rule-threshold" }}
            errors={conditionErrors}
          />
          {delayField}
          {!isBitTest && (
            <div className="space-y-1 md:col-span-2">
              <Label htmlFor="rule-deadband">Deadband (clear hysteresis)</Label>
              <Input id="rule-deadband" inputMode="decimal" value={deadband} onChange={e => setDeadband(e.target.value)}
                aria-invalid={!!errors.deadband} aria-describedby="rule-deadband-error" />
              <FieldError id="rule-deadband-error" message={errors.deadband} />
            </div>
          )}
        </div>
      )}

      {kind === "condition" && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
          <div className="md:col-span-6">
            <ConditionGroup group={group} onChange={setGroup} points={points} errorsFor={key => groupErrors[key]} label="Raise when" />
          </div>
          {delayField}
          <p className="self-end pb-2 text-xs text-muted-foreground md:col-span-4">Clears as soon as the condition no longer holds.</p>
        </div>
      )}

      {kind === "comms_stale" && (
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
            value={message} maxLength={500} onChange={e => setMessage(e.target.value)} />
        </div>
      </div>

      <div className="flex flex-wrap items-start gap-x-10 gap-y-3">
        <div className="space-y-1">
          <Label>Notifications</Label>
          <div className="flex flex-wrap items-center gap-3">
            <NotificationToggles value={notify} onChange={setNotify} label="Notifications for this rule" />
            <span className="text-xs text-muted-foreground">Sent when the rule raises an alarm, on each selected channel.</span>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-6">
          <Checkbox id="rule-enabled" checked={enabled && canEnableThis} disabled={!canEnableThis} onCheckedChange={checked => setEnabled(checked === true)} />
          <Label htmlFor="rule-enabled" className="font-normal">
            Enabled: evaluated and shown in Active alarms{!canEnableThis && " (the site already has the maximum enabled; disable a rule first)"}
          </Label>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button onClick={handleSave} disabled={isSaving}>{isSaving ? "Saving..." : isEdit ? "Save changes" : "Save rule"}</Button>
      </div>
    </section>
  );
}
