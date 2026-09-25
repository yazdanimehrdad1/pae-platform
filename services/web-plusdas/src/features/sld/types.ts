// Layout-only device data (static, from layout JSON)
export interface SLDDeviceLayout {
  id: string;
  type: "grid" | "bus" | "transformer" | "breaker" | "pv" | "bess" | "generator" | "load" | "wind";
  name: string;
  voltage: string;
  properties?: Record<string, unknown>;
  position?: {
    x: number;
    y: number;
    level?: number;
    branch?: number;
  };
}

// Data-only device information (dynamic, from API)
export interface SLDDeviceData {
  id: string;
  status?: "online" | "warning" | "offline";
  power?: string;
  powerFlow?: {
    direction: "export" | "import" | "generate" | "consume" | "charge" | "discharge";
    valueKW: number;
  };
  properties?: Record<string, unknown>;
}

// Combined device (merged from layout + data)
export interface SLDDevice {
  id: string;
  type: "grid" | "bus" | "transformer" | "breaker" | "pv" | "bess" | "generator" | "load" | "wind";
  name: string;
  voltage: string;
  status: "online" | "warning" | "offline";
  power?: string;
  powerFlow?: {
    direction: "export" | "import" | "generate" | "consume" | "charge" | "discharge";
    valueKW: number;
  };
  properties?: Record<string, unknown>;
  // convertSLDData sets only level/branch; x/y come from the layout when present
  // (MicrogridSLD checks both for undefined before using them).
  position?: {
    x?: number;
    y?: number;
    level?: number;
    branch?: number;
  };
}

export interface SLDConnection {
  from: string;
  to: string;
  flowDirection?: "down" | "up" | "left" | "right";
  fromPoint?: {
    side: "top" | "bottom" | "left" | "right";
    position?: "left" | "middle" | "right" | "center";
  };
  toPoint?: {
    side: "top" | "bottom" | "left" | "right";
    position?: "left" | "middle" | "right" | "center";
  };
}

export interface SLDBus {
  id: string;
  label: string;
  voltage: string;
  position?: {
    x: number;
    y: number;
    width: number;
  };
  level?: number;
  width?: string;
}

export interface SLDSummary {
  label: string;
  value: string | number;
  subtext?: string;
  color?: string;
  icon?: string;
  trend?: {
    value: number;
    direction: "up" | "down" | "neutral";
  };
}

export interface SLDLayout {
  siteId?: string;
  siteName?: string;
  devices: SLDDeviceLayout[];
  connections: SLDConnection[];
  buses: SLDBus[];
}

export interface SLDDataInfo {
  siteId?: string;
  devices: SLDDeviceData[];
  summary?: SLDSummary[];
}

export interface SLDData {
  siteId?: string;
  siteName?: string;
  devices: SLDDevice[];
  connections: SLDConnection[];
  buses: SLDBus[];
  summary?: SLDSummary[];
}
