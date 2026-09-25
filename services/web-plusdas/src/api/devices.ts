import type { Device, DeviceRecord, DeviceCreateRequest, DeviceUpdateRequest, DeviceDeleteResponse, DeviceScanRanges } from '@/shared/types/device';
import type { DevicePoint, DevicePointCreateRequest, DevicePointUpdateRequest } from '@/shared/types/device-point';
import type { components } from '@contracts/backend-ot';
import { client, request } from './client';

function toDevice(device: DeviceRecord): Device {
  const points = [
    ...device.points.standardized,
    ...device.points.native,
    ...device.points.virtual,
  ].map(point => point.name);
  return {
    id: String(device.device_id),
    name: device.name,
    type: device.type.toLowerCase() as Device['type'],
    status: 'online',
    location: device.host,
    lastUpdate: device.updated_at,
    points,
    make: device.vendor,
    model: device.model,
    serialNumber: String(device.device_id),
    commStatus: device.poll_enabled ? 'connected' : 'timeout',
    firmware: '',
    protocol: device.protocol,
    description: device.description,
    modbusConfig: device.protocol.toLowerCase() === 'modbus' ? {
      port: device.port,
      serverAddress: device.server_address,
      pollEnabled: device.poll_enabled,
      readFromAggregator: device.read_from_aggregator,
      addressMode: device.modbus_address_mode,
      scanRangesLocked: device.scan_ranges_locked,
      scanRanges: device.scan_ranges ? {
        holding: device.scan_ranges.holding.map(r => ({ startIndex: r.start_index, count: r.count })),
        input: device.scan_ranges.input.map(r => ({ startIndex: r.start_index, count: r.count })),
        coils: device.scan_ranges.coils.map(r => ({ startIndex: r.start_index, count: r.count })),
      } : null,
    } : undefined,
  };
}

export interface DevicePointsEntry {
  deviceId: number;
  deviceName: string;
  points: Array<{ id: number; name: string; category: string }>;
}

export const devicesApi = {
  getBySite: async (siteId: string): Promise<Device[]> => {
    try {
      const data = await client.get<DeviceRecord[]>(`/devices/site/${siteId}/devices`);
      return data.map(toDevice);
    } catch (error: unknown) {
      const apiError = error as { detail?: string };
      if (apiError?.detail?.toLowerCase().startsWith('no devices found')) return [];
      throw error;
    }
  },

  ping: (siteId: string, deviceId: string): Promise<PingResult> =>
    client.get(`/healthz/site/${siteId}/device/${deviceId}`),

  getBySiteWithPoints: async (siteId: string): Promise<DevicePointsEntry[]> => {
    try {
      const data = await client.get<DeviceRecord[]>(`/devices/site/${siteId}/devices`);
      return data.map(device => ({
        deviceId: device.device_id,
        deviceName: device.name,
        points: [
          ...device.points.standardized,
          ...device.points.native,
          ...device.points.virtual,
        ],
      }));
    } catch (error: unknown) {
      const apiError = error as { detail?: string };
      if (apiError?.detail?.toLowerCase().startsWith('no devices found')) return [];
      throw error;
    }
  },

  list: async (siteId: string): Promise<DeviceRecord[]> => {
    try {
      return await client.get<DeviceRecord[]>(`/devices/site/${siteId}/devices?include_deleted=true`);
    } catch (error: unknown) {
      const apiError = error as { detail?: string };
      if (apiError?.detail?.toLowerCase().startsWith('no devices found')) return [];
      throw error;
    }
  },

  create: (siteId: string, payload: DeviceCreateRequest): Promise<DeviceRecord> =>
    client.post(`/devices/site/${siteId}/devices`, payload),

  update: (siteId: string, deviceId: number, payload: DeviceUpdateRequest): Promise<DeviceRecord> =>
    client.put(`/devices/site/${siteId}/devices/${deviceId}`, payload),

  remove: (siteId: string, deviceId: number, opts: { mode: 'soft' | 'hard'; confirm?: boolean }): Promise<DeviceDeleteResponse> => {
    const params = new URLSearchParams({ mode: opts.mode, confirm: String(opts.confirm ?? false) });
    return request<DeviceDeleteResponse>(`/devices/site/${siteId}/devices/${deviceId}?${params}`, { method: 'DELETE' });
  },

  restore: (siteId: string, deviceId: number): Promise<DeviceRecord> =>
    client.post(`/devices/site/${siteId}/devices/${deviceId}/restore`, {}),

  getRecord: (siteId: string, deviceId: number): Promise<DeviceRecord> =>
    client.get(`/devices/site/${siteId}/devices/${deviceId}?include_deleted=true`),

  setScanRanges: (siteId: string, deviceId: number, ranges: DeviceScanRanges): Promise<DeviceScanRanges> =>
    client.put(`/device-points/site/${siteId}/device/${deviceId}/scan-ranges`, ranges),

  resetScanRanges: (siteId: string, deviceId: number): Promise<DeviceScanRanges> =>
    request<DeviceScanRanges>(`/device-points/site/${siteId}/device/${deviceId}/scan-ranges`, { method: 'DELETE' }),

  getPoints: (siteId: string, deviceId: number, opts?: { include_deleted?: boolean }): Promise<DevicePoint[]> => {
    const params = new URLSearchParams();
    if (opts?.include_deleted) params.set('include_deleted', 'true');
    return client.get(`/device-points/site/${siteId}/device/${deviceId}?${params}`);
  },

  createPoint: (siteId: string, deviceId: number, payload: DevicePointCreateRequest): Promise<DevicePoint[]> =>
    client.put(`/device-points/site/${siteId}/device/${deviceId}/bulk`, { points: [payload] }),

  bulkUpsertPoints: (siteId: string, deviceId: number, payloads: DevicePointCreateRequest[]): Promise<DevicePoint[]> =>
    client.put(`/device-points/site/${siteId}/device/${deviceId}/bulk`, { points: payloads }),

  updatePoint: (siteId: string, deviceId: number, pointId: number, payload: DevicePointUpdateRequest): Promise<DevicePoint> =>
    client.put(`/device-points/site/${siteId}/device/${deviceId}/${pointId}`, payload),

  deletePoints: (siteId: string, deviceId: number, pointIds: number[], opts: { mode: 'soft' | 'hard'; confirm?: boolean }): Promise<DevicePoint[]> => {
    // point_ids is an integer array in the contract: repeat the parameter (?point_ids=1&point_ids=2).
    // A comma-joined value is rejected with 422 for more than one id.
    const params = new URLSearchParams({ mode: opts.mode, confirm: String(opts.confirm ?? false) });
    for (const pointId of pointIds) params.append('point_ids', String(pointId));
    return request<DevicePoint[]>(`/device-points/site/${siteId}/device/${deviceId}?${params}`, { method: 'DELETE' });
  },

  restorePoint: (siteId: string, deviceId: number, pointId: number): Promise<DevicePoint> =>
    client.post(`/device-points/site/${siteId}/device/${deviceId}/${pointId}/restore`, {}),
};

export type PingResult = components['schemas']['DeviceHealthStatus'];
