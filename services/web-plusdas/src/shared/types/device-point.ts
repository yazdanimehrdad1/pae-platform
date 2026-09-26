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
