import { Zap, Power, Shield, Activity, Grid3X3, Gauge, Sun, Battery, Workflow, Cpu } from "lucide-react";

export const deviceTypeConfig = {
  transformer: { icon: Zap, color: 'text-primary', bgColor: 'bg-primary/10' },
  generator: { icon: Power, color: 'text-secondary', bgColor: 'bg-secondary/10' },
  protection: { icon: Shield, color: 'text-accent', bgColor: 'bg-accent/10' },
  feeder: { icon: Activity, color: 'text-success', bgColor: 'bg-success/10' },
  switch: { icon: Grid3X3, color: 'text-warning', bgColor: 'bg-warning/10' },
  meter: { icon: Gauge, color: 'text-destructive', bgColor: 'bg-destructive/10' },
  pv: { icon: Sun, color: 'text-yellow-500', bgColor: 'bg-yellow-500/10' },
  bess: { icon: Battery, color: 'text-green-500', bgColor: 'bg-green-500/10' },
  relay: { icon: Workflow, color: 'text-blue-500', bgColor: 'bg-blue-500/10' },
  rtac: { icon: Cpu, color: 'text-purple-500', bgColor: 'bg-purple-500/10' },
  inverter: { icon: Sun, color: 'text-orange-500', bgColor: 'bg-orange-500/10' },
};
