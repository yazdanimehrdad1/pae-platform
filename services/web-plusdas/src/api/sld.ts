import type { SLDLayout, SLDDataInfo } from '@/features/sld/types';
import { client } from './client';

export const sldApi = {
  getLayout: (siteId: string): Promise<SLDLayout> =>
    client.get(`/sites/${siteId}/sld/layout`),

  getData: (siteId: string): Promise<SLDDataInfo> =>
    client.get(`/sites/${siteId}/sld/data`),
};
