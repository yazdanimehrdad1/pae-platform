import type { Site, SiteRecord, SiteCreateRequest, SiteUpdateRequest, SiteDeleteResponse } from '@/shared/types/site';
import { client, request } from './client';

interface BackendSite {
  site_id: number;
  name: string;
  location: { street: string; city: string; state: string; zip_code: number };
  operator: string;
  capacity: string;
  device_count: number;
  description: string;
  last_update: string;
  status?: 'online' | 'warning' | 'offline';
  type?: Site['type'];
}

function toSite(site: BackendSite): Site {
  return {
    id: String(site.site_id),
    name: site.name,
    location: `${site.location.city}, ${site.location.state}`,
    type: site.type ?? 'facility',
    status: site.status ?? 'online',
    deviceCount: site.device_count,
    lastUpdate: site.last_update,
    capacity: site.capacity,
    operator: site.operator,
    description: site.description,
  };
}

export const sitesApi = {
  getAll: async (): Promise<Site[]> => {
    const data = await client.get<BackendSite[]>('/sites');
    return data.map(toSite);
  },

  getById: async (siteId: string): Promise<Site> => {
    const data = await client.get<BackendSite>(`/sites/${siteId}`);
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
};
