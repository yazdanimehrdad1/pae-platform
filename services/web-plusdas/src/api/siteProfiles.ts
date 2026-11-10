import type {
  ApproveChangesRequest, PendingChanges, ProfileVersion, ProfileVersionSummary, SiteFunctionTestRunRequest,
  SiteFunctionTestRunResponse, SiteProfileStatus,
} from './types/siteProfiles';
import { intelliGatewayClient } from './client';

// Site profiles: what the AI (intelli-gateway) knows of each site's facts, the changes in
// backend-ot that wait for approval, and approving them. Admins only (the gateway answers 403 to
// anyone else). Reading backend-ot here ("sync") never changes what the AI sees: only an approval does.
const profilePath = (siteId: number) => `/v1/sites/${siteId}/profile`;

export const siteProfilesApi = {
  list: (): Promise<SiteProfileStatus[]> => intelliGatewayClient.get('/v1/site-profiles'),
  syncAll: (): Promise<SiteProfileStatus[]> => intelliGatewayClient.post('/v1/site-profiles/sync', {}),
  /** The approved profile; rejects with 404 while the site isn't onboarded. */
  get: (siteId: number): Promise<ProfileVersion> => intelliGatewayClient.get(profilePath(siteId)),
  versions: (siteId: number): Promise<ProfileVersionSummary[]> =>
    intelliGatewayClient.get(`${profilePath(siteId)}/versions`),
  /** Rejects with 404 until backend-ot was read for this site. */
  changes: (siteId: number): Promise<PendingChanges> => intelliGatewayClient.get(`${profilePath(siteId)}/changes`),
  sync: (siteId: number): Promise<PendingChanges> => intelliGatewayClient.post(`${profilePath(siteId)}/sync`, {}),
  /** 409 when backend-ot was read again after `fetched_at`: review the changes again. */
  approve: (siteId: number, body: ApproveChangesRequest): Promise<ProfileVersion> =>
    intelliGatewayClient.post(`${profilePath(siteId)}/approve`, body),
  /** Runs an approved site function exactly as the AI would (backend-ot computes it); the result
   * is what the AI gets, series summarized. 404: not an approved function; 422: bad request. */
  testRunFunction: (siteId: number, name: string, body: SiteFunctionTestRunRequest): Promise<SiteFunctionTestRunResponse> =>
    intelliGatewayClient.post(`/v1/sites/${siteId}/functions/${encodeURIComponent(name)}/test-run`, body),
};
