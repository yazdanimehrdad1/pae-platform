import type { DevicePoint } from './device-point';

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

export interface RegisterRange {
  start_index: number;
  count: number;
}

export interface DeviceScanRanges {
  holding: RegisterRange[];
  input: RegisterRange[];
  coils: RegisterRange[];
}

export interface DeviceRecord {
  device_id: number;
  site_id: number;
  name: string;
  type: 'meter' | 'relay' | 'RTAC' | 'inverter' | 'BESS';
  protocol: 'Modbus' | 'DNP';
  vendor: string | null;
  model: string | null;
  host: string;
  port: number;
  timeout: number | null;
  server_address: number;
  description: string | null;
  poll_enabled: boolean;
  read_from_aggregator: boolean;
  scan_ranges: DeviceScanRanges | null;
  scan_ranges_locked: boolean;
  modbus_address_mode: 'zero_based' | 'one_based';
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  points: { standardized: DevicePoint[]; native: DevicePoint[]; virtual: DevicePoint[] };
}

export interface DeviceCreateRequest {
  name: string;
  type: DeviceRecord['type'];
  protocol?: DeviceRecord['protocol'];
  vendor?: string;
  model?: string;
  host: string;
  port?: number;
  timeout?: number;
  server_address?: number;
  description?: string;
  poll_enabled?: boolean;
  read_from_aggregator?: boolean;
  modbus_address_mode?: DeviceRecord['modbus_address_mode'];
}

export type DeviceUpdateRequest = Partial<DeviceCreateRequest>;

export interface DeviceDeleteResponse {
  device_id: number;
  site_id: number;
  mode: 'soft' | 'hard';
}
