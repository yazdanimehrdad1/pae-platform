import type {
  DeviceFactsRequest, DocumentCreated, DocumentRequest, KnowledgeCoverage, KnowledgeState, KnowledgeVersion,
  KnowledgeVersionSummary, PointGuideRequest, SiteScriptCreated, SiteScriptRequest,
} from './types/knowledge';
import { intelliGatewayClient } from './client';

// A site's engineer knowledge (intelli-gateway): point guides, documents and device ratings.
// Admins only. Every edit goes to the site's draft and answers with the whole state; the AI reads
// only what is published, and a publish takes the whole draft. `draft_revision` is the revision
// the edit was made against: a 409 means someone saved in between (reload).
const base = (siteId: number) => `/v1/sites/${siteId}/knowledge`;
const revisionQuery = (draftRevision?: number) =>
  draftRevision === undefined ? '' : `?draft_revision=${draftRevision}`;
const guidePath = (siteId: number, deviceId: number, pointName: string) =>
  `${base(siteId)}/point-guides/${deviceId}/${encodeURIComponent(pointName)}`;

export const knowledgeApi = {
  /** Rejects with 404 while the site isn't onboarded. */
  get: (siteId: number): Promise<KnowledgeState> => intelliGatewayClient.get(base(siteId)),
  coverage: (siteId: number): Promise<KnowledgeCoverage> => intelliGatewayClient.get(`${base(siteId)}/coverage`),

  putPointGuide: (siteId: number, deviceId: number, pointName: string, body: PointGuideRequest): Promise<KnowledgeState> =>
    intelliGatewayClient.put(guidePath(siteId, deviceId, pointName), body),
  deletePointGuide: (siteId: number, deviceId: number, pointName: string, draftRevision?: number): Promise<KnowledgeState> =>
    intelliGatewayClient.deleteJson(`${guidePath(siteId, deviceId, pointName)}${revisionQuery(draftRevision)}`),

  createDocument: (siteId: number, body: DocumentRequest): Promise<DocumentCreated> =>
    intelliGatewayClient.post(`${base(siteId)}/documents`, body),
  updateDocument: (siteId: number, documentId: string, body: DocumentRequest): Promise<KnowledgeState> =>
    intelliGatewayClient.put(`${base(siteId)}/documents/${encodeURIComponent(documentId)}`, body),
  deleteDocument: (siteId: number, documentId: string, draftRevision?: number): Promise<KnowledgeState> =>
    intelliGatewayClient.deleteJson(`${base(siteId)}/documents/${encodeURIComponent(documentId)}${revisionQuery(draftRevision)}`),

  /** Site scripts: the admin's general information about the site, in order (a new one goes last). */
  createSiteScript: (siteId: number, body: SiteScriptRequest): Promise<SiteScriptCreated> =>
    intelliGatewayClient.post(`${base(siteId)}/site-scripts`, body),
  updateSiteScript: (siteId: number, scriptId: string, body: SiteScriptRequest): Promise<KnowledgeState> =>
    intelliGatewayClient.put(`${base(siteId)}/site-scripts/${encodeURIComponent(scriptId)}`, body),
  deleteSiteScript: (siteId: number, scriptId: string, draftRevision?: number): Promise<KnowledgeState> =>
    intelliGatewayClient.deleteJson(`${base(siteId)}/site-scripts/${encodeURIComponent(scriptId)}${revisionQuery(draftRevision)}`),

  putDeviceFacts: (siteId: number, deviceId: number, body: DeviceFactsRequest): Promise<KnowledgeState> =>
    intelliGatewayClient.put(`${base(siteId)}/device-facts/${deviceId}`, body),
  deleteDeviceFacts: (siteId: number, deviceId: number, draftRevision?: number): Promise<KnowledgeState> =>
    intelliGatewayClient.deleteJson(`${base(siteId)}/device-facts/${deviceId}${revisionQuery(draftRevision)}`),

  /** Put these draft changes back as published. */
  revert: (siteId: number, itemKeys: string[], draftRevision?: number): Promise<KnowledgeState> =>
    intelliGatewayClient.post(`${base(siteId)}/draft/revert`, { item_keys: itemKeys, draft_revision: draftRevision }),
  discardDraft: (siteId: number): Promise<KnowledgeState> => intelliGatewayClient.deleteJson(`${base(siteId)}/draft`),
  /** The whole draft becomes the next version; the AI uses it from now on. */
  publish: (siteId: number, draftRevision?: number): Promise<KnowledgeVersion> =>
    intelliGatewayClient.post(`${base(siteId)}/publish`, { draft_revision: draftRevision }),

  versions: (siteId: number): Promise<KnowledgeVersionSummary[]> => intelliGatewayClient.get(`${base(siteId)}/versions`),
  /** Publishes an earlier version's content again, as a new version (409 while there is a draft). */
  restore: (siteId: number, version: number): Promise<KnowledgeVersion> =>
    intelliGatewayClient.post(`${base(siteId)}/versions/${version}/restore`, {}),
  /** Deletes older versions (never the one the AI uses: 422); returns the versions left. */
  deleteVersions: (siteId: number, versions: number[]): Promise<KnowledgeVersionSummary[]> =>
    intelliGatewayClient.deleteJson(`${base(siteId)}/versions?${versions.map(version => `version=${version}`).join('&')}`),
};
