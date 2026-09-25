import type { Site, SiteRecord, SiteCreateRequest, SiteUpdateRequest, SiteDeleteResponse } from '@/shared/types/site';
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
    capacity: site.capacity,
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
};
