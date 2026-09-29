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
