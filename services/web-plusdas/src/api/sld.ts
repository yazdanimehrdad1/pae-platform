import type {
  SiteSld,
  SiteSldResponse,
  SiteSldUpsertRequest,
  SldNotFoundDetail,
  SldValuesResponse,
} from './types/sld';
import { client } from './client';

// backend-ot's code for "the site exists but has no diagram yet" (not an error for the UI). Typed
// from the contract, so a rename in backend-ot fails the typecheck here.
const NO_SLD_ERROR: SldNotFoundDetail['error'] = 'SiteSldNotFoundError';

function isNoSldError(error: unknown): boolean {
  return (error as { detail?: Partial<SldNotFoundDetail> })?.detail?.error === NO_SLD_ERROR;
}

export const sldApi = {
  // The site's stored single line diagram and its revision; null if the site has none yet.
  getBySite: async (siteId: string | number): Promise<SiteSldResponse | null> => {
    try {
      return await client.get<SiteSldResponse>(`/sites/${siteId}/sld`);
    } catch (error: unknown) {
      if (isNoSldError(error)) return null;
      throw error;
    }
  },

  // Create the site's diagram (revision null) or replace the revision that was read (409 if stale).
  save: (siteId: string | number, sld: SiteSld, revision: number | null): Promise<SiteSldResponse> => {
    const body: SiteSldUpsertRequest = { sld, revision };
    return client.put<SiteSldResponse>(`/sites/${siteId}/sld`, body);
  },

  // Live values of the elements linked to devices, for the info boxes. Poll it.
  getValues: (siteId: string | number): Promise<SldValuesResponse> =>
    client.get<SldValuesResponse>(`/sites/${siteId}/sld/values`),
};
