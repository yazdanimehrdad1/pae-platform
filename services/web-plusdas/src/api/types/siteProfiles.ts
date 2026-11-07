import type { components } from '@contracts/intelli-gateway';

type Schemas = components['schemas'];

// Wire types: generated from intelli-gateway's contract (it owns the AI's site profiles).
export type SiteProfileStatus = Schemas['SiteProfileStatus'];
export type PendingChanges = Schemas['PendingChanges'];
export type ProfileChange = Schemas['ProfileChange'];
export type ProfileVersion = Schemas['ProfileVersion'];
export type ProfileVersionSummary = Schemas['ProfileVersionSummary'];
export type ApproveChangesRequest = Schemas['ApproveChangesRequest'];
export type ProfilePoint = Schemas['PointInfo'];
export type ProfileDevice = Schemas['Device'];
export type ChangeKind = Schemas['ChangeKind'];
export type ChangeTarget = Schemas['ChangeTarget'];
