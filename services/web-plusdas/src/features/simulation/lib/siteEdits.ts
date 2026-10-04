import type { SimulationConfig, SiteConfig } from '@/api/types/powerflow';

// The only site settings the Simulation page may change: it selects from what exists and never
// adds assets or changes ratings, topology or point lists. Saving writes the full config back
// (powerflow's PUT /sites/{name} replaces the whole document), so every other field must come
// through untouched.

export interface ProfileChoice {
  scenario: string;
  scale: number;
}

export interface SiteEdits {
  simulation: {
    step_s: number;
    start_time: string;
    seed: number;
    autostart: boolean;
    test_mode: boolean;
    history_size: number;
  };
  loadProfiles: Record<string, ProfileChoice>; // load id → profile
  pvProfiles: Record<string, ProfileChoice>; // PV id → availability profile
  modbusEnabled: boolean;
}

// powerflow's defaults (SimulationConfig), for a stored config that omits a field.
const SIMULATION_DEFAULTS: SiteEdits['simulation'] = {
  step_s: 1,
  start_time: '2026-01-01T00:00:00Z',
  seed: 0,
  autostart: true,
  test_mode: false,
  history_size: 3600,
};

export function editsFromConfig(config: SiteConfig): SiteEdits {
  const simulation: Partial<SimulationConfig> = config.simulation ?? {};
  return {
    simulation: {
      step_s: simulation.step_s ?? SIMULATION_DEFAULTS.step_s,
      start_time: simulation.start_time ?? SIMULATION_DEFAULTS.start_time,
      seed: simulation.seed ?? SIMULATION_DEFAULTS.seed,
      autostart: simulation.autostart ?? SIMULATION_DEFAULTS.autostart,
      test_mode: simulation.test_mode ?? SIMULATION_DEFAULTS.test_mode,
      history_size: simulation.history_size ?? SIMULATION_DEFAULTS.history_size,
    },
    loadProfiles: Object.fromEntries(
      (config.loads ?? []).map((load) => [
        load.id,
        { scenario: load.profile.scenario, scale: load.profile.scale ?? 1 },
      ]),
    ),
    pvProfiles: Object.fromEntries(
      (config.pv ?? []).map((pv) => [
        pv.id,
        { scenario: pv.availability.scenario, scale: pv.availability.scale ?? 1 },
      ]),
    ),
    modbusEnabled: config.interfaces?.modbus?.enabled ?? false,
  };
}

/** The config with only the allowed fields replaced; everything else is carried over as is. */
export function applySiteEdits(config: SiteConfig, edits: SiteEdits): SiteConfig {
  const next: SiteConfig = structuredClone(config);
  next.simulation = { ...next.simulation, ...edits.simulation };
  next.loads = next.loads?.map((load) => {
    const choice = edits.loadProfiles[load.id];
    return choice ? { ...load, profile: { ...load.profile, ...choice } } : load;
  });
  next.pv = next.pv?.map((pv) => {
    const choice = edits.pvProfiles[pv.id];
    return choice ? { ...pv, availability: { ...pv.availability, ...choice } } : pv;
  });
  next.interfaces = {
    ...next.interfaces,
    modbus: { ...next.interfaces?.modbus, enabled: edits.modbusEnabled },
  };
  return next;
}

/** Whether saving these edits changes anything (to enable the Save button). */
export function hasChanges(config: SiteConfig, edits: SiteEdits): boolean {
  return JSON.stringify(editsFromConfig(config)) !== JSON.stringify(edits);
}
