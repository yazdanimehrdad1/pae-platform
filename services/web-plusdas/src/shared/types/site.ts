import type { components } from '@contracts/backend-ot';

type Schemas = components['schemas'];

// UI view model (what the pages render); built from SiteRecord in src/api/sites.ts.
export interface Site {
  id: string;
  name: string;
  location: string;
  type: 'substation' | 'plant' | 'microgrid' | 'solar' | 'wind' | 'facility';
  status: 'online' | 'warning' | 'offline';
  deviceCount: number;
  lastUpdate: string;
  capacity: string;
  operator: string;
  description: string;
}

// Wire types: generated from backend-ot's contract, never hand-written.
export type SiteLocation = Schemas['Location'];
export type SiteCoordinates = Schemas['Coordinates'];
export type SiteRecord = Schemas['SiteResponse'];
export type SiteCreateRequest = Schemas['SiteCreateRequest'];
export type SiteUpdateRequest = Schemas['SiteUpdateRequest'];
export type SiteDeleteResponse = Schemas['SiteDeleteResponse'];
