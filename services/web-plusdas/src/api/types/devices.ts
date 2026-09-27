import type { components } from '@contracts/backend-ot';
import type { DevicePoint } from './devicePoints';

type Schemas = components['schemas'];

// UI view model (what the pages render); built from DeviceRecord in src/api/devices.ts.
export interface Device {
  id: string;
  name: string;
  type: 'transformer' | 'generator' | 'protection' | 'feeder' | 'switch' | 'meter' | 'pv' | 'bess' | 'relay' | 'rtac' | 'inverter';
  status: 'online' | 'warning' | 'offline' | 'fault';
  location: string;
  lastUpdate: string;
  points: string[];
  make: string;
  model: string;
  serialNumber: string;
  commStatus: 'connected' | 'timeout' | 'error';
  firmware: string;
  protocol?: string;
  description?: string;
  modbusConfig?: {
    port: number;
    serverAddress: number;
    pollEnabled: boolean;
    readFromAggregator: boolean;
    addressMode: string;
    scanRangesLocked: boolean;
    scanRanges: {
      holding: Array<{ startIndex: number; count: number }>;
      input: Array<{ startIndex: number; count: number }>;
      coils: Array<{ startIndex: number; count: number }>;
    } | null;
  };
}

// Wire types: generated from backend-ot's contract, never hand-written.
export type RegisterRange = Schemas['RegisterRange'];
export type DeviceScanRanges = Schemas['DeviceScanRanges'];
export type DeviceRecord = Schemas['DeviceWithPoints'];
export type DeviceType = Schemas['DeviceCreateRequest']['type'];
export type DeviceCreateRequest = Schemas['DeviceCreateRequest'];
export type DeviceUpdateRequest = Schemas['DeviceUpdate'];
export type DeviceDeleteResponse = Schemas['DeviceDeleteResponse'];
export type PingResult = Schemas['DeviceHealthStatus'];

// Point categories in the order the asset tree lists them.
export const POINT_GROUP_ORDER = ['standardized', 'virtual', 'native'] as const;
export type PointGroup = (typeof POINT_GROUP_ORDER)[number];

// Points of one device, as the asset tree lists them (built in src/api/devices.ts).
// `groups` is sorted by name within each category; `points` is the same items flattened
// in POINT_GROUP_ORDER.
export interface DevicePointsEntry {
  deviceId: number;
  deviceName: string;
  groups: Record<PointGroup, DevicePoint[]>;
  points: DevicePoint[];
}
