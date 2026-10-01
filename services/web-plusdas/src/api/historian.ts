import type { DevicePointReadingsRequest, BackendPointReadings, LatestPointReadings } from './types/historian';
import { client } from './client';

export const historianApi = {
  getDevicePointReadings: (req: DevicePointReadingsRequest): Promise<BackendPointReadings> => {
    const params = new URLSearchParams({ point_ids: req.pointIds.join(',') });
    if ('timeRange' in req) {
      params.set('time_range', req.timeRange);
    } else {
      params.set('start_time', req.startTime);
      params.set('end_time', req.endTime);
    }
    return client.get(
      `/device-point-readings/timeseries/site/${req.siteId}/device/${req.deviceId}?${params}`
    );
  },

  /** The newest `limit` readings of every point of a device (virtual points computed), newest first. */
  getRecentReadings: (siteId: string, deviceId: string, limit: number): Promise<BackendPointReadings> =>
    client.get(`/device-point-readings/timeseries/site/${siteId}/device/${deviceId}?${new URLSearchParams({ limit: String(limit) })}`),

  /** The newest stored reading of each of a device's points. */
  getLatestReadings: (siteId: string, deviceId: string): Promise<LatestPointReadings> =>
    client.get(`/device-point-readings/site/${siteId}/device/${deviceId}/latest`),
};
