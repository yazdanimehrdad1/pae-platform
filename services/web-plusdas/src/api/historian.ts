import type { TimeSeriesRequest, TimeSeriesResponse, DevicePointReadingsRequest, BackendPointReadings } from '@/shared/types/api';
import { client } from './client';

export const historianApi = {
  getTimeSeries: (req: TimeSeriesRequest): Promise<TimeSeriesResponse[]> =>
    client.post(`/sites/${req.siteId}/historian/timeseries`, req),

  getAssetTree: (siteId: string): Promise<Record<string, unknown>> =>
    client.get(`/sites/${siteId}/historian/asset-tree`),

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
};
