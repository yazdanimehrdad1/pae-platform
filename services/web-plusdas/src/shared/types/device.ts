import type { components } from '@contracts/backend-ot';

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
