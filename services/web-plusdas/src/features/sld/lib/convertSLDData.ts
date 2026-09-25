import type { SLDData, SLDDevice, SLDBus, SLDConnection, SLDSummary } from "../types";

export function convertToSLDData(jsonData: {
  nodes: Array<{
    id: string;
    type: string;
    name: string;
    voltage: string;
    position?: { x: number; y: number };
    layout?: { layer?: string; order?: number };
    powerFlow?: { direction: string; valueKW: number };
    properties?: Record<string, unknown>;
    ui?: { color?: string; state?: string };
  }>;
  edges: Array<{ id: string; source: string; target: string }>;
  metadata?: Record<string, unknown>;
}): SLDData {
  const devices: SLDDevice[] = [];
  const connections: SLDConnection[] = [];
  const buses: SLDBus[] = [];

  const layerOrder = ["grid", "medium-voltage", "protection", "transformation", "low-voltage", "der", "load"];
  const layerToLevel = new Map<string, number>();
  layerOrder.forEach((layer, idx) => layerToLevel.set(layer, idx));

  jsonData.nodes.forEach((node, idx) => {
    const layer = node.layout?.layer || "default";
    const level = layerToLevel.get(layer) ?? 0;
    const order = node.layout?.order ?? idx;

    if (node.type === "bus") {
      buses.push({
        id: node.id,
        label: node.name.toUpperCase(),
        voltage: node.voltage,
        level,
        width: level === 3 ? "w-[90%] max-w-[700px]" : "w-[60%] max-w-[500px]"
      });
    } else {
      const device: SLDDevice = {
        id: node.id,
        type: node.type as SLDDevice["type"],
        name: node.name,
        voltage: node.voltage,
        status: (node.properties?.status as string) === "online" ||
                (node.properties?.status as string) === "closed"
          ? "online"
          : (node.properties?.status as string) === "warning"
          ? "warning"
          : "offline",
        power: node.powerFlow ? `${node.powerFlow.valueKW} kW` : node.voltage,
        powerFlow: node.powerFlow ? {
          direction: node.powerFlow.direction as SLDDevice["powerFlow"]["direction"],
          valueKW: node.powerFlow.valueKW
        } : undefined,
        properties: node.properties || {},
        position: { level, branch: order }
      };
      devices.push(device);
    }
  });

  jsonData.edges.forEach(edge => {
    connections.push({ from: edge.source, to: edge.target });
  });

  const summary: SLDSummary[] = [];
  const totalGeneration = devices.filter(d => d.powerFlow?.direction === "generate").reduce((s, d) => s + (d.powerFlow?.valueKW || 0), 0);
  const gridImport = devices.filter(d => d.type === "grid" && d.powerFlow?.direction === "import").reduce((s, d) => s + (d.powerFlow?.valueKW || 0), 0);
  const totalLoad = devices.filter(d => d.powerFlow?.direction === "consume").reduce((s, d) => s + (d.powerFlow?.valueKW || 0), 0);
  const battery = devices.find(d => d.type === "bess");
  const batteryFlow = battery?.powerFlow;

  if (totalGeneration > 0) summary.push({ label: "Total Generation", value: `${totalGeneration} kW`, subtext: "Renewable Sources", color: "text-accent" });
  if (gridImport > 0) summary.push({ label: "Grid Import", value: `${gridImport} kW`, subtext: "From Utility", color: "text-primary" });
  if (totalLoad > 0) summary.push({ label: "Total Load", value: `${totalLoad} kW`, subtext: "All Consumers", color: "text-foreground" });
  if (battery && batteryFlow) summary.push({ label: "Battery", value: batteryFlow.direction === "charge" ? "Charging" : "Discharging", subtext: `${batteryFlow.direction === "charge" ? "+" : "-"}${batteryFlow.valueKW} kW`, color: "text-warning" });

  return {
    siteName: (jsonData.metadata?.name as string) || "Microgrid System",
    devices,
    connections,
    buses: buses.sort((a, b) => (a.level ?? 0) - (b.level ?? 0)),
    summary
  };
}
