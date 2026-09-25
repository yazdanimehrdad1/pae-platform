import React, { useRef } from "react";
import {
  Zap,
  Sun,
  Wind,
  Battery,
  Building2,
  Home,
  AlertTriangle,
  ArrowDownUp,
  Power,
} from "lucide-react";
import { SLDNode } from "./SLDNode";
import { SVGConnection } from "./SVGConnection";
import { BusBar } from "./BusBar";
import type { SLDData, SLDDevice, SLDBus, SLDConnection } from "../types";

interface MicrogridSLDProps {
  data: SLDData;
  boundary?: {
    minX?: number;
    maxX?: number;
    minY?: number;
    maxY?: number;
  };
}

const DEVICE_WIDTH = 140;
const DEVICE_HEIGHT = 150;
const BUS_HEIGHT = 12;
const LEVEL_SPACING = 150;
const BRANCH_SPACING = 200;

const getDeviceIcon = (type: string) => {
  switch (type) {
    case "grid": return <Zap className="w-5 h-5" />;
    case "pv": return <Sun className="w-5 h-5 text-solar" />;
    case "wind": return <Wind className="w-5 h-5 text-wind" />;
    case "bess": return <Battery className="w-5 h-5 text-warning" />;
    case "generator": return <Power className="w-5 h-5" />;
    case "transformer": return <ArrowDownUp className="w-5 h-5" />;
    case "load": return <Home className="w-5 h-5" />;
    default: return <Power className="w-5 h-5" />;
  }
};

const getDeviceVariant = (type: string): "grid" | "solar" | "wind" | "battery" | "load" | "transformer" => {
  switch (type) {
    case "grid": return "grid";
    case "pv": return "solar";
    case "wind": return "wind";
    case "bess": return "battery";
    case "transformer": return "transformer";
    case "load":
    default: return "load";
  }
};

const getBusWidth = (width?: string): number => {
  if (!width) return 700;
  const maxWidthMatch = width.match(/max-w-\[(\d+)px\]/);
  if (maxWidthMatch) return parseInt(maxWidthMatch[1], 10);
  return 700;
};

const getDevicePosition = (device: SLDDevice): { x: number; y: number } => {
  if (device.position?.x !== undefined && device.position?.y !== undefined) {
    return { x: device.position.x, y: device.position.y };
  }
  const level = device.position?.level ?? 0;
  const branch = device.position?.branch ?? 0;
  const centerX = 400;
  return { x: centerX + (branch - 1) * BRANCH_SPACING, y: 100 + level * LEVEL_SPACING };
};

const getBusPosition = (bus: SLDBus): { x: number; y: number; width: number } => {
  if (bus.position?.x !== undefined && bus.position?.y !== undefined && bus.position?.width !== undefined) {
    return { x: bus.position.x, y: bus.position.y, width: bus.position.width };
  }
  const level = bus.level ?? 2;
  const width = getBusWidth(bus.width);
  return { x: 400, y: 100 + level * LEVEL_SPACING, width };
};

const getDeviceSidesMiddlePoints = (device: SLDDevice) => {
  const pos = getDevicePosition(device);
  const halfWidth = DEVICE_WIDTH / 2;
  const halfHeight = DEVICE_HEIGHT / 2;
  return {
    top: { x: pos.x, y: pos.y - halfHeight },
    bottom: { x: pos.x, y: pos.y + halfHeight },
    left: { x: pos.x - halfWidth, y: pos.y },
    right: { x: pos.x + halfWidth, y: pos.y },
  };
};

const getDeviceConnectionPoint = (
  device: SLDDevice,
  side: "top" | "bottom" | "left" | "right",
  position?: "left" | "middle" | "right" | "center"
): { x: number; y: number } => {
  const middlePoints = getDeviceSidesMiddlePoints(device);
  const pos = getDevicePosition(device);
  const halfWidth = DEVICE_WIDTH / 2;
  const halfHeight = DEVICE_HEIGHT / 2;

  if (!position || position === "middle" || position === "center") return middlePoints[side];

  if (side === "top" || side === "bottom") {
    const y = side === "top" ? pos.y - halfHeight : pos.y + halfHeight;
    if (position === "left") return { x: pos.x - halfWidth, y };
    if (position === "right") return { x: pos.x + halfWidth, y };
  }

  if (side === "left" || side === "right") {
    const x = side === "left" ? pos.x - halfWidth : pos.x + halfWidth;
    if (position === "left") return { x, y: pos.y - halfHeight };
    if (position === "right") return { x, y: pos.y + halfHeight };
  }

  return middlePoints[side];
};

const getBusConnectionPoint = (
  bus: SLDBus,
  side: "top" | "bottom" | "left" | "right",
  position: "left" | "middle" | "right" | "center" | undefined,
  connectedDeviceX?: number
): { x: number; y: number } => {
  const busPos = getBusPosition(bus);
  const busWidth = busPos.width;
  const busLeft = busPos.x - busWidth / 2;
  const busRight = busPos.x + busWidth / 2;

  let x = busPos.x;
  if (connectedDeviceX !== undefined) {
    x = Math.max(busLeft, Math.min(busRight, connectedDeviceX));
  } else {
    if (position === "left") x = busLeft + busWidth / 4;
    else if (position === "right") x = busLeft + (3 * busWidth) / 4;
  }

  let y = busPos.y;
  if (side === "top") y = busPos.y - BUS_HEIGHT / 2;
  else if (side === "bottom") y = busPos.y + BUS_HEIGHT / 2;

  return { x, y };
};

const getConnectionPoint = (
  elementId: string,
  side: "top" | "bottom" | "left" | "right",
  position: "left" | "middle" | "right" | "center" | undefined,
  deviceMap: Map<string, SLDDevice>,
  busMap: Map<string, SLDBus>,
  connectedDeviceX?: number
): { x: number; y: number } => {
  const device = deviceMap.get(elementId);
  if (device) return getDeviceConnectionPoint(device, side, position);
  const bus = busMap.get(elementId);
  if (bus) return getBusConnectionPoint(bus, side, position, connectedDeviceX);
  return { x: 400, y: 0 };
};

export const MicrogridSLD = ({ data, boundary }: MicrogridSLDProps) => {
  const { devices, connections, buses } = data;

  const boundaryMinX = boundary?.minX ?? -500;
  const boundaryMaxX = boundary?.maxX ?? 1500;
  const boundaryMinY = boundary?.minY ?? -200;
  const boundaryMaxY = boundary?.maxY ?? 1200;

  const containerRef = useRef<HTMLDivElement>(null);

  const deviceMap = new Map(devices.map(d => [d.id, d]));
  const busMap = new Map(buses.map(b => [b.id, b]));

  const allX = [
    ...devices.map(d => getDevicePosition(d).x),
    ...buses.map(b => { const p = getBusPosition(b); return [p.x - p.width / 2, p.x + p.width / 2]; }).flat()
  ];
  const allY = [
    ...devices.map(d => getDevicePosition(d).y),
    ...buses.map(b => getBusPosition(b).y)
  ];

  const minX = boundary ? boundaryMinX : Math.min(...allX, 0) - 200;
  const maxX = boundary ? boundaryMaxX : Math.max(...allX, 0) + 200;
  const minY = boundary ? boundaryMinY : Math.min(...allY, 0) - 100;
  const maxY = boundary ? boundaryMaxY : Math.max(...allY, 0) + 200;

  const canvasWidth = maxX - minX;
  const canvasHeight = maxY - minY;

  return (
    <div className="bg-background">
      <div>
        <div
          ref={containerRef}
          className="relative border-2 border-dashed border-muted-foreground/30 rounded-lg overflow-hidden"
          style={{
            width: `${canvasWidth}px`,
            height: `${canvasHeight}px`,
            minHeight: "800px",
            backgroundColor: "hsl(var(--background))",
          }}
        >
          {connections.map((connection, idx) => {
            const fromDevice = deviceMap.get(connection.from);
            const fromBus = busMap.get(connection.from);
            const toDevice = deviceMap.get(connection.to);
            const toBus = busMap.get(connection.to);

            let fromPointDeviceX: number | undefined;
            let toPointDeviceX: number | undefined;

            if (fromBus && toDevice) fromPointDeviceX = getDevicePosition(toDevice).x;
            if (toBus && fromDevice) toPointDeviceX = getDevicePosition(fromDevice).x;

            const fromPoint = connection.fromPoint
              ? getConnectionPoint(connection.from, connection.fromPoint.side, connection.fromPoint.position, deviceMap, busMap, fromPointDeviceX)
              : getConnectionPoint(connection.from, "bottom", undefined, deviceMap, busMap, fromPointDeviceX);

            const toPoint = connection.toPoint
              ? getConnectionPoint(connection.to, connection.toPoint.side, connection.toPoint.position, deviceMap, busMap, toPointDeviceX)
              : getConnectionPoint(connection.to, "top", undefined, deviceMap, busMap, toPointDeviceX);

            const adjustedX1 = fromPoint.x - minX;
            const adjustedY1 = fromPoint.y - minY;
            const adjustedX2 = toPoint.x - minX;
            const adjustedY2 = toPoint.y - minY;

            let powerFlowDirection: "export" | "import" | "generate" | "consume" | "charge" | "discharge" | undefined;
            if (fromDevice?.powerFlow) powerFlowDirection = fromDevice.powerFlow.direction;
            else if (toDevice?.powerFlow) powerFlowDirection = toDevice.powerFlow.direction;

            return (
              <SVGConnection
                key={`${connection.from}-${connection.to}-${Math.round(adjustedX1)}-${Math.round(adjustedY1)}-${Math.round(adjustedX2)}-${Math.round(adjustedY2)}`}
                x1={adjustedX1}
                y1={adjustedY1}
                x2={adjustedX2}
                y2={adjustedY2}
                flowDirection={connection.flowDirection || "down"}
                powerFlowDirection={powerFlowDirection}
              />
            );
          })}

          {buses.map(bus => {
            const busPos = getBusPosition(bus);
            return (
              <div key={bus.id}>
                <div
                  className="absolute select-none"
                  style={{
                    left: `${busPos.x - minX - busPos.width / 2}px`,
                    top: `${busPos.y - minY - BUS_HEIGHT / 2}px`,
                    width: `${busPos.width}px`,
                    height: `${BUS_HEIGHT}px`,
                    zIndex: 5,
                  }}
                >
                  <BusBar label={`${bus.label} (${bus.voltage})`} width="w-full" />
                </div>
              </div>
            );
          })}

          {devices.map(device => {
            const pos = getDevicePosition(device);
            return (
              <div key={device.id}>
                <div
                  className="absolute select-none"
                  style={{
                    left: `${pos.x - minX - DEVICE_WIDTH / 2}px`,
                    top: `${pos.y - minY - DEVICE_HEIGHT / 2}px`,
                    zIndex: 5,
                  }}
                >
                  <SLDNode
                    title={device.name}
                    icon={getDeviceIcon(device.type)}
                    power={device.power || device.voltage}
                    status={device.status}
                    variant={getDeviceVariant(device.type)}
                    className={
                      device.type === "load" && device.properties?.priority === "HIGH"
                        ? "border-destructive"
                        : device.type === "load" && device.properties?.priority === "MEDIUM"
                        ? "border-load-commercial"
                        : undefined
                    }
                  >
                    {device.powerFlow && (
                      <div className="mt-2 text-xs text-muted-foreground font-mono">
                        {device.powerFlow.direction}: {device.powerFlow.valueKW} kW
                      </div>
                    )}
                    {device.type === "bess" && device.properties?.soc !== undefined && (
                      <div className="mt-2">
                        <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                          <div
                            className="h-full bg-warning rounded-full transition-all"
                            style={{ width: `${device.properties.soc}%` }}
                          />
                        </div>
                        <div className="text-xs text-muted-foreground font-mono mt-1">
                          SOC: {String(device.properties.soc)}% | {String(device.properties.capacity || "N/A")}
                        </div>
                      </div>
                    )}
                    {device.properties && Object.keys(device.properties).length > 0 && !device.powerFlow && device.type !== "bess" && (
                      <div className="mt-2 text-xs text-muted-foreground font-mono">
                        {device.properties.capacity && <div>Capacity: {String(device.properties.capacity)}</div>}
                        {device.properties.priority && <div>Priority: {String(device.properties.priority)}</div>}
                      </div>
                    )}
                  </SLDNode>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
