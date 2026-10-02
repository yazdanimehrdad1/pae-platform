import type { SiteSldResponse } from './types/sld';
import { client } from './client';

export const sldApi = {
  // The site's stored single line diagram and its revision. 404 if the site has none.
  getBySite: (siteId: string | number): Promise<SiteSldResponse> =>
    client.get<SiteSldResponse>(`/sites/${siteId}/sld`),
};
