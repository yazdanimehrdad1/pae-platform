import type { SiteSld } from './types/sld';
import { client } from './client';

export const sldApi = {
  // The site's single line diagram, from its profile. 404 if the profile has none.
  getBySite: (siteId: string | number): Promise<SiteSld> => client.get<SiteSld>(`/sites/${siteId}/sld`),
};
