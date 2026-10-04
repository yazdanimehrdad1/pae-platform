import type {
  AssetsResponse,
  BessAssetResponse,
  BessSetpointRequest,
  ConditionChange,
  ConditionsReport,
  DeviceHistory,
  DeviceKind,
  DevicesSnapshot,
  EngineStatus,
  EventScenario,
  EventScenarioSummary,
  ModbusRegistersResponse,
  ProfileFolder,
  ProfileScenarios,
  PvAssetResponse,
  PvSetpointRequest,
  SetpointResult,
  SiteConfig,
  SiteList,
  Snapshot,
} from './types/powerflow';
import { powerflowClient as api } from './client';

const site = (name: string) => `/sites/${encodeURIComponent(name)}`;

// The powerflow simulator (same-origin /powerflow-api, forwarded to powerflow's /api).
export const powerflowApi = {
  // -- simulation engine -----------------------------------------------------------------------
  getStatus: () => api.get<EngineStatus>('/sim/status'),
  // `at` (ISO time) schedules the start; omitted = now.
  start: (at?: string) => api.post<EngineStatus>('/sim/start', at ? { at } : {}),
  setSpeed: (speed: number) => api.put<EngineStatus>('/sim/speed', { speed }),
  pause: () => api.post<EngineStatus>('/sim/pause', {}),
  stop: () => api.post<EngineStatus>('/sim/stop', {}),
  reset: () => api.post<EngineStatus>('/sim/reset', {}),
  // Manual stepping: only for a site in test mode, and only while not running.
  step: (count: number) => api.post<unknown>(`/sim/step?count=${count}`, {}),

  // -- injected conditions and event scenarios -------------------------------------------------
  getConditions: () => api.get<ConditionsReport>('/sim/conditions'),
  applyCondition: (change: ConditionChange) => api.post<ConditionsReport>('/sim/conditions', change),
  clearConditions: () => api.post<ConditionsReport>('/sim/conditions/clear', {}),
  startEventScenario: (name: string) => api.post<ConditionsReport>('/sim/event-scenario/start', { name }),
  stopEventScenario: () => api.post<ConditionsReport>('/sim/event-scenario/stop', {}),
  listEventScenarios: (siteName: string) => api.get<EventScenarioSummary[]>(`${site(siteName)}/event-scenarios`),
  getEventScenario: (siteName: string, name: string) =>
    api.get<EventScenario>(`${site(siteName)}/event-scenarios/${encodeURIComponent(name)}`),
  saveEventScenario: (siteName: string, name: string, scenario: EventScenario) =>
    api.put<EventScenario>(`${site(siteName)}/event-scenarios/${encodeURIComponent(name)}`, scenario),
  deleteEventScenario: (siteName: string, name: string) =>
    api.delete(`${site(siteName)}/event-scenarios/${encodeURIComponent(name)}`),

  // -- sites -----------------------------------------------------------------------------------
  listSites: () => api.get<SiteList>('/sites'),
  getSite: (name: string) => api.get<SiteConfig>(site(name)),
  // Replaces the whole stored config (the active site needs the simulation stopped).
  saveSite: (name: string, config: SiteConfig) => api.put<SiteConfig>(site(name), config),
  deleteSite: (name: string) => api.delete(site(name)),
  // Loads a stored site into the engine (simulation must be stopped) and restarts the interfaces.
  activateSite: (name: string) => api.post<SiteConfig>(`${site(name)}/activate`, {}),

  // -- profile scenarios (view only) -----------------------------------------------------------
  listProfiles: () => api.get<ProfileScenarios>('/profiles'),
  getProfileCsv: (folder: ProfileFolder, scenario: string) =>
    api.getText(`/profiles/${folder}/${encodeURIComponent(scenario)}`),

  // -- measurements of the active site ---------------------------------------------------------
  // The native snapshot (powerflow's names, kW, 0-based codes).
  getLatestSnapshot: () => api.get<Snapshot>('/measurements/latest'),
  // The PAE point-standard view: every device's standard points (SI units, standard codes).
  listDevices: () => api.get<DevicesSnapshot>('/devices'),
  getDeviceHistory: (kind: DeviceKind, assetId: string, points: string[]) => {
    const query = new URLSearchParams(points.map((point) => ['points', point]));
    return api.get<DeviceHistory>(`/devices/${kind}/${encodeURIComponent(assetId)}/history?${query}`);
  },

  // -- Modbus (view only) ----------------------------------------------------------------------
  getModbusRegisters: () => api.get<ModbusRegistersResponse>('/modbus/registers'),

  // -- assets of the active site and their setpoints -------------------------------------------
  getAssets: () => api.get<AssetsResponse>('/assets'),
  getBess: (id: string) => api.get<BessAssetResponse>(`/assets/bess/${encodeURIComponent(id)}`),
  getPv: (id: string) => api.get<PvAssetResponse>(`/assets/pv/${encodeURIComponent(id)}`),
  setBess: (id: string, request: BessSetpointRequest) =>
    api.put<SetpointResult>(`/assets/bess/${encodeURIComponent(id)}/setpoint`, request),
  setPv: (id: string, request: PvSetpointRequest) =>
    api.put<SetpointResult>(`/assets/pv/${encodeURIComponent(id)}/setpoint`, request),
};
