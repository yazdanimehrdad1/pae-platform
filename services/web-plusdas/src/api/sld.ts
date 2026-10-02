import type { SiteSldResponse, SldValuesResponse } from './types/sld';
import { client } from './client';

export const sldApi = {
  // The site's stored single line diagram and its revision. 404 if the site has none.
  getBySite: (siteId: string | number): Promise<SiteSldResponse> =>
    client.get<SiteSldResponse>(`/sites/${siteId}/sld`),

  // Live values of the elements linked to devices, for the info boxes. Poll it.
  getValues: (siteId: string | number): Promise<SldValuesResponse> =>
    client.get<SldValuesResponse>(`/sites/${siteId}/sld/values`),
};
