import type { components } from '@contracts/intelli-gateway';

type Schemas = components['schemas'];

// Wire types: generated from intelli-gateway's contract (it owns the engineer knowledge).
export type KnowledgeState = Schemas['KnowledgeStateResponse'];
export type DocumentCreated = Schemas['DocumentCreatedResponse'];
export type SiteKnowledgeContent = Schemas['SiteKnowledge'];
export type KnowledgeChange = Schemas['KnowledgeChange'];
export type KnowledgeCoverage = Schemas['KnowledgeCoverage'];
export type KnowledgeVersion = Schemas['KnowledgeVersion'];
export type KnowledgeVersionSummary = Schemas['KnowledgeVersionSummary'];
export type PointGuide = Schemas['PointGuide'];
export type PointGuideRequest = Schemas['PointGuideRequest'];
export type StateGuide = Schemas['StateGuide'];
export type LimitGuide = Schemas['LimitGuide'];
export type KnowledgeDocument = Schemas['KnowledgeDocument'];
export type DocumentRequest = Schemas['DocumentRequest'];
export type SitePrompt = Schemas['SitePrompt'];
export type SitePromptRequest = Schemas['SitePromptRequest'];
export type SitePromptCreated = Schemas['SitePromptCreatedResponse'];
export type SitePromptLinks = Schemas['SitePromptLinks'];
export type DeviceFacts = Schemas['DeviceFacts'];
export type DeviceFactsRequest = Schemas['DeviceFactsRequest'];
export type DeviceRating = Schemas['DeviceRating'];
export type GuideSeverity = Schemas['GuideSeverity'];
export type StateKind = Schemas['StateKind'];
export type KnowledgeKind = Schemas['KnowledgeKind'];
export type LimitCondition = Schemas['LimitCondition'];
