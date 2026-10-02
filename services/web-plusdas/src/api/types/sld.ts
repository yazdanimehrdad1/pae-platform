import type { components } from '@contracts/backend-ot';

type Schemas = components['schemas'];

// Wire types: a site's single line diagram, generated from backend-ot's contract.
export type SiteSld = Schemas['SiteSld'];
export type SldNode = Schemas['SldNode'];
export type SldBus = Schemas['SldBus'];
export type SldConnection = Schemas['SldConnection'];
export type SldNodeType = SldNode['type'];
