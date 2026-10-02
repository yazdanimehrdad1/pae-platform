import type { SldNodeType, SldNodeValues, SldValue } from "@/api/types/sld";

// What an element's info box shows, in order. A row reads one role's value, or the device health.
export type InfoRow =
  | { kind: "value"; label: string; role: string; unit?: string }
  | { kind: "health"; label: string };

const VOLTS = "V";
const AMPS = "A";

// Only these element types get an info box (when linked to a device).
export const INFO_ROWS: Partial<Record<SldNodeType, InfoRow[]>> = {
  meter: [
    { kind: "value", label: "VAB", role: "vab", unit: VOLTS },
    { kind: "value", label: "VBC", role: "vbc", unit: VOLTS },
    { kind: "value", label: "VCA", role: "vca", unit: VOLTS },
    { kind: "value", label: "IA", role: "ia", unit: AMPS },
    { kind: "value", label: "IB", role: "ib", unit: AMPS },
    { kind: "value", label: "IC", role: "ic", unit: AMPS },
    { kind: "value", label: "IN", role: "in", unit: AMPS },
  ],
  bess: [
    { kind: "value", label: "SOC", role: "soc", unit: "%" },
    { kind: "value", label: "Power", role: "power", unit: "kW" },
    { kind: "value", label: "Mode", role: "mode" },
    { kind: "health", label: "Health" },
  ],
  pv: [
    { kind: "value", label: "Power", role: "power", unit: "kW" },
    { kind: "health", label: "Health" },
    { kind: "value", label: "Sun", role: "irradiance", unit: "W/m²" },
  ],
};

export const NOT_AVAILABLE = "NA";

function formatNumber(value: number): string {
  const magnitude = Math.abs(value);
  const decimals = magnitude >= 100 ? 0 : magnitude >= 10 ? 1 : 2;
  return value.toFixed(decimals);
}

/** A value row's text: the enum label, or the number with its unit; NA when there is no value. */
export function formatRowValue(value: SldValue | null | undefined, fallbackUnit?: string): string {
  if (!value || value.value === null || value.value === undefined) return NOT_AVAILABLE;
  if (value.label) return value.label;
  const unit = value.unit ?? fallbackUnit;
  return unit ? `${formatNumber(value.value)} ${unit}` : formatNumber(value.value);
}

export type HealthState = "healthy" | "unhealthy" | "unknown";

export function healthState(nodeValues: SldNodeValues | undefined): HealthState {
  const healthy = nodeValues?.health?.healthy;
  if (healthy === true) return "healthy";
  if (healthy === false) return "unhealthy";
  return "unknown";
}
