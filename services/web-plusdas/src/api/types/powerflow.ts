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
// Runtime battery overrides: SOC now, and round-trip efficiency (null = the site config's).
export type BessBatteryRequest = Schemas['BessBatteryRequest'];
export type BessBatteryState = Schemas['BessBatteryState'];

// Injected conditions (breakers, faults, alarm resets, comm loss, grid events) and event scenarios
export type ConditionsReport = Schemas['ConditionsReport'];
export type BreakerStatus = Schemas['BreakerStatus'];
export type FaultCause = Schemas['FaultCause'];
export type FaultSeverity = Schemas['Severity'];
export type FaultStatus = Schemas['FaultStatus'];
// The fault cause catalog: what each cause does on a BESS or PV (GET /sim/fault-causes).
export type FaultCauseInfo = Schemas['FaultCauseInfo'];
export type FaultAssetType = FaultCauseInfo['asset_type'];
export type CommTarget = Schemas['CommTarget'];
export type BreakerChange = Schemas['BreakerChange'];
export type AssetFaultChange = Schemas['AssetFaultChange'];
export type AlarmResetChange = Schemas['AlarmResetChange'];
export type CommLossChange = Schemas['CommLossChange'];
export type GridVoltageChange = Schemas['GridVoltageChange'];
export type GridFrequencyChange = Schemas['GridFrequencyChange'];
export type ConditionChange =
  | BreakerChange
  | AssetFaultChange
  | AlarmResetChange
  | CommLossChange
  | GridVoltageChange
  | GridFrequencyChange;
export type EventScenario = Schemas['EventScenario'];
export type ScenarioEvent = Schemas['ScenarioEvent'];
// What one point-standard point should read while a scenario plays (checked by step).
export type ExpectedPoint = Schemas['ExpectedPoint'];
export type EventScenarioSummary = Schemas['EventScenarioSummary'];
export type EventScenarioCategory = Schemas['EventScenarioCategory'];
export type ScenarioStatus = Schemas['ScenarioStatus'];

// Auto dispatch: every BESS cycles between its SOC limits on its own (no setpoints needed)
export type AutoDispatchRequest = Schemas['AutoDispatchRequest'];
export type AutoDispatchReport = Schemas['AutoDispatchReport'];
export type AutoDispatchBess = Schemas['AutoDispatchBess'];
export type AutoDispatchDirection = Schemas['AutoDispatchDirection'];
export type AutoDispatchPhase = Schemas['AutoDispatchPhase'];
// Site-wide defaults, or one BESS's overrides (every field optional; omitted = fall back).
export type AutoDispatchBessSettings = Schemas['AutoDispatchBessSettings'];

// Measurements: the native snapshot, and the PAE point-standard device view
export type Snapshot = Schemas['Snapshot'];
export type DevicesSnapshot = Schemas['DevicesSnapshot'];
export type DeviceReadings = Schemas['DeviceReadings'];
export type PointReading = Schemas['PointReading'];
export type DeviceKind = DeviceReadings['kind'];
export type DeviceHistory = Schemas['DeviceHistory'];
