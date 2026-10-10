import type {
  Site, SiteRecord, SiteCreateRequest, SiteUpdateRequest, SiteDeleteResponse, SiteHealth, PointSeverity,
} from './types/sites';
import { client, request } from './client';

// backend-ot has no site type or status yet (see docs/backend-gaps.md), so the UI defaults them.
function toSite(site: SiteRecord): Site {
  return {
    id: String(site.site_id),
    name: site.name,
    location: site.location ? `${site.location.city}, ${site.location.state}` : '',
    type: 'facility',
    status: 'online',
    deviceCount: site.device_count,
    lastUpdate: site.last_update,
    operator: site.operator,
    description: site.description ?? '',
  };
}

export const sitesApi = {
  getAll: async (): Promise<Site[]> => {
    const data = await client.get<SiteRecord[]>('/sites');
    return data.map(toSite);
  },

  getById: async (siteId: string): Promise<Site> => {
    const data = await client.get<SiteRecord>(`/sites/${siteId}`);
    return toSite(data);
  },

  list: (): Promise<SiteRecord[]> => client.get<SiteRecord[]>('/sites?include_deleted=true'),

  create: (payload: SiteCreateRequest): Promise<SiteRecord> => client.post('/sites', payload),

  update: (siteId: number, payload: SiteUpdateRequest): Promise<SiteRecord> =>
    client.put(`/sites/${siteId}`, payload),

  remove: (siteId: number, opts: { mode: 'soft' | 'hard'; confirm?: boolean }): Promise<SiteDeleteResponse> => {
    const params = new URLSearchParams({ mode: opts.mode, confirm: String(opts.confirm ?? false) });
    return request<SiteDeleteResponse>(`/sites/${siteId}?${params}`, { method: 'DELETE' });
  },

  restore: (siteId: number): Promise<SiteRecord> => client.post(`/sites/${siteId}/restore`, {}),

  // The site's ALARM-class points that are set, per device. No filter = all severities / all devices.
  getHealth: (
    siteId: string,
    filters: { severity?: PointSeverity[]; deviceIds?: number[] } = {},
  ): Promise<SiteHealth> => {
    const params = new URLSearchParams();
    filters.severity?.forEach((severity) => params.append('severity', severity));
    filters.deviceIds?.forEach((deviceId) => params.append('device_ids', String(deviceId)));
    const query = params.toString();
    return client.get<SiteHealth>(`/sites/${siteId}/health${query ? `?${query}` : ''}`);
  },
};
