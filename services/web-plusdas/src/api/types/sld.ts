import type { components } from '@contracts/backend-ot';

type Schemas = components['schemas'];

// Wire types: a site's single line diagram, generated from backend-ot's contract.
export type SiteSld = Schemas['SiteSld'];
// The stored diagram with its revision (send it back on save).
export type SiteSldResponse = Schemas['SiteSldResponse'];
// Create or replace a site's diagram, naming the revision it replaces (null to create).
export type SiteSldUpsertRequest = Schemas['SiteSldUpsertRequest'];
export type SldNode = Schemas['SldNode'];
export type SldBus = Schemas['SldBus'];
export type SldConnection = Schemas['SldConnection'];
export type SldDeviceLink = Schemas['SldDeviceLink'];
export type SldNodeType = SldNode['type'];

// Live values of the elements linked to devices (GET /sites/{id}/sld/values).
export type SldValuesResponse = Schemas['SldValuesResponse'];
export type SldNodeValues = Schemas['SldNodeValues'];
export type SldValue = Schemas['SldValue'];
export type DeviceHealth = Schemas['DeviceHealth'];

// The 404 detail of the SLD routes; its error code tells "no diagram yet" from "no such site".
export type SldNotFoundDetail = Schemas['SldNotFoundDetail'];
