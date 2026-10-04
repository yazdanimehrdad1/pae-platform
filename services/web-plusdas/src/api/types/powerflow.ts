import type { components } from '@contracts/powerflow';

type Schemas = components['schemas'];

// Wire types of the powerflow simulator, generated from its contract
// (contracts/openapi/powerflow.openapi.json). Fields with server defaults are optional here.

// Simulation engine
export type EngineStatus = Schemas['EngineStatus'];
export type RunState = EngineStatus['state'];

// Sites (stored configurations) and the active one
export type SiteList = Schemas['SiteList'];
export type SiteConfig = Schemas['SiteConfig'];
export type SimulationConfig = Schemas['SimulationConfig'];
export type GridConfig = Schemas['GridConfig'];
export type LineConfig = Schemas['LineConfig'];
export type CollectorConfig = Schemas['CollectorConfig'];
export type TransformerConfig = Schemas['TransformerConfig'];
export type BessConfig = Schemas['BessConfig'];
export type PvConfig = Schemas['PvConfig'];
export type LoadConfig = Schemas['LoadConfig'];
export type MeterConfig = Schemas['MeterConfig'];

// Profile scenarios (CSV files)
export type ProfileScenarios = Schemas['ProfileScenarios'];
export type ProfileFolder = 'load' | 'pv';

// Modbus: the aggregator server's layout
export type ModbusRegistersResponse = Schemas['ModbusRegistersResponse'];
export type ModbusDevice = Schemas['ModbusDevice'];
export type ModbusRegister = Schemas['ModbusRegister'];

// Assets of the active site and their setpoints
export type AssetsResponse = Schemas['AssetsResponse'];
export type BessAssetResponse = Schemas['BessAssetResponse'];
export type PvAssetResponse = Schemas['PvAssetResponse'];
export type LoadAssetResponse = Schemas['LoadAssetResponse'];
export type BessSetpointRequest = Schemas['BessSetpointRequest'];
export type PvSetpointRequest = Schemas['PvSetpointRequest'];
export type SetpointResult = Schemas['SetpointResult'];
export type BessMode = NonNullable<BessSetpointRequest['mode']>;
