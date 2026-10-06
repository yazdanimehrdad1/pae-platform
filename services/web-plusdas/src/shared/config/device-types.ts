import { Activity, Battery, BatteryCharging, CircuitBoard, Cpu, Gauge, Power, Sun, Workflow, type LucideIcon } from "lucide-react";
import type { DeviceTypeKey } from "@/api/types/devices";

interface DeviceTypeStyle {
  label: string;
  icon: LucideIcon;
  color: string;
  bgColor: string;
}

// One entry per backend-ot device type (a Record over the contract's enum), so a new type
// fails `make typecheck` here instead of crashing the pages that look a device's type up.
export const deviceTypeConfig: Record<DeviceTypeKey, DeviceTypeStyle> = {
  bess: { label: "BESS", icon: Battery, color: "text-green-500", bgColor: "bg-green-500/10" },
  es: { label: "Energy storage", icon: BatteryCharging, color: "text-green-600", bgColor: "bg-green-600/10" },
  pv: { label: "PV", icon: Sun, color: "text-yellow-500", bgColor: "bg-yellow-500/10" },
  inverter: { label: "Inverter", icon: Sun, color: "text-orange-500", bgColor: "bg-orange-500/10" },
  generator: { label: "Generator", icon: Power, color: "text-secondary", bgColor: "bg-secondary/10" },
  loadbank: { label: "Load bank", icon: Activity, color: "text-success", bgColor: "bg-success/10" },
  meter: { label: "Meter", icon: Gauge, color: "text-destructive", bgColor: "bg-destructive/10" },
  relay: { label: "Relay", icon: Workflow, color: "text-blue-500", bgColor: "bg-blue-500/10" },
  ied: { label: "IED", icon: CircuitBoard, color: "text-sky-500", bgColor: "bg-sky-500/10" },
  rtac: { label: "RTAC", icon: Cpu, color: "text-purple-500", bgColor: "bg-purple-500/10" },
};
