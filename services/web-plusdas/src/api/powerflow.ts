import type {
  AssetsResponse,
  BessAssetResponse,
  BessSetpointRequest,
  EngineStatus,
  ModbusRegistersResponse,
  ProfileFolder,
  ProfileScenarios,
  PvAssetResponse,
  PvSetpointRequest,
  SetpointResult,
  SiteConfig,
  SiteList,
} from './types/powerflow';
import { powerflowClient as api } from './client';

const site = (name: string) => `/sites/${encodeURIComponent(name)}`;

// The powerflow simulator (same-origin /powerflow-api, forwarded to powerflow's /api).
export const powerflowApi = {
  // -- simulation engine -----------------------------------------------------------------------
  getStatus: () => api.get<EngineStatus>('/sim/status'),
  start: () => api.post<EngineStatus>('/sim/start', {}),
  pause: () => api.post<EngineStatus>('/sim/pause', {}),
  stop: () => api.post<EngineStatus>('/sim/stop', {}),
  reset: () => api.post<EngineStatus>('/sim/reset', {}),
  // Manual stepping: only for a site in test mode, and only while not running.
  step: (count: number) => api.post<unknown>(`/sim/step?count=${count}`, {}),

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
