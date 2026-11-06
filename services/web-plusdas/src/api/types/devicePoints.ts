import type { components } from '@contracts/backend-ot';

type Schemas = components['schemas'];

// Wire types: generated from backend-ot's contract, never hand-written.
export type DevicePoint = Schemas['DevicePointResponse'];
export type DevicePointCategory = Schemas['DevicePointCreateRequest']['category'];
export type DevicePointDataType = Schemas['DevicePointCreateRequest']['data_type'];
export type DevicePointClass = NonNullable<Schemas['DevicePointCreateRequest']['class']>;
export type DevicePointSeverity = NonNullable<Schemas['DevicePointCreateRequest']['severity']>;
export type DevicePointCreateRequest = Schemas['DevicePointCreateRequest'];
export type DevicePointUpdateRequest = Schemas['DevicePointUpdateRequest'];

// A device's NATIVE points as CSV: GET .../csv (export), GET /device-points/csv-template, and
// POST .../csv-import (a dry run by default) answering what the import does or did.
export type PointsCsvImportResult = Schemas['PointsCsvImportResult'];
export type PointsCsvProblem = Schemas['PointsCsvProblem'];

// Standardized points: linked to a NATIVE point on their device through PUT/DELETE .../{point_id}/link.
export type StandardizedPointLinkRequest = Schemas['StandardizedPointLinkRequest'];

// Virtual points: created and updated through their own routes, with a condition or calculation.
export type VirtualPointCreateRequest = Schemas['VirtualPointCreateRequest'];
export type VirtualPointUpdateRequest = Schemas['VirtualPointUpdateRequest'];
export type VirtualPointDefinitionInput = VirtualPointCreateRequest['definition'];
export type VirtualPointDefinition = NonNullable<DevicePoint['virtual_definition']>;
export type VirtualConditionDefinitionInput = Schemas['VirtualConditionDefinition-Input'];
export type VirtualConditionGroupInput = Schemas['VirtualConditionGroup-Input'];
export type VirtualConditionGroupOutput = Schemas['VirtualConditionGroup-Output'];
export type VirtualCondition = Schemas['VirtualCondition'];
export type VirtualCalculationDefinition = Schemas['VirtualCalculationDefinition'];
export type VirtualCalculationFunction = VirtualCalculationDefinition['function'];
