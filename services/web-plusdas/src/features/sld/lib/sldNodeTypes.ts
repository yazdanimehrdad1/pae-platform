import type { SldNodeType } from "@/api/types/sld";

// Labels for the contract's element types (a new type in backend-ot fails the typecheck here).
export const NODE_TYPE_LABELS: Record<SldNodeType, string> = {
  grid: "Utility grid",
  poi: "Point of interconnection",
  meter: "Meter",
  transformer: "Transformer",
  breaker: "Breaker",
  switch: "Switch",
  pv: "PV",
  inverter: "Inverter",
  bess: "BESS",
  generator: "Generator",
  wind: "Wind",
  load: "Load",
  plant_controller: "Plant controller",
};
