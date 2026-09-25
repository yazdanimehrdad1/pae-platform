import type { HealthStateResponse } from '@/shared/types/api';
import { client } from './client';

export const healthApi = {
  getStates: (siteId: string, deviceIds: string[]): Promise<HealthStateResponse[]> =>
    client.post(`/sites/${siteId}/health`, { deviceIds }),

  getStateByDevice: (siteId: string, deviceId: string): Promise<HealthStateResponse> =>
    client.get(`/sites/${siteId}/health/${deviceId}`),
};
