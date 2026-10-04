import type { SiteConfig } from '@/api/types/powerflow';

const transformer = (kva: number) => ({
  s_rated_kva: kva,
  vn_hv_kv: 12.47,
  vn_lv_kv: 0.48,
  z_pct: 5.75,
  x_r: 7,
  no_load_loss_kw: 2.5,
  i0_pct: 0.2,
});

const bess = (id: string) => ({
  id,
  name: id.toUpperCase(),
  collector: 'mv1',
  inverter: { s_rated_kva: 2750, p_discharge_max_kw: 2500, p_charge_max_kw: 2500, v_lv_kv: 0.48 },
  battery: { capacity_kwh: 10000, soc_min_pct: 5, soc_max_pct: 95, soc_initial_pct: 50, aux_load_kw: 15 },
  transformer: transformer(2750),
});

// Shaped like powerflow's reference_2bess_1pv: POI line, one collector tied by a switch, two BESS
// and a PV with feeder meters, and a load on the POI.
export const REFERENCE_SITE: SiteConfig = {
  schema_version: 1,
  site: { name: 'Reference site' },
  simulation: {
    step_s: 1,
    start_time: '2026-06-21T06:00:00Z',
    autostart: true,
    test_mode: false,
    seed: 42,
    history_size: 3600,
  },
  grid: { vn_kv: 12.47, vm_pu: 1, va_degree: 0, sc_mva: 100, x_r: 5 },
  poi: { line: { length_km: 0.5, r_ohm_per_km: 0.306, x_ohm_per_km: 0.35, c_nf_per_km: 0, max_i_ka: 0.6 } },
  collectors: [{ id: 'mv1' }],
  bess: [bess('bess1'), bess('bess2')],
  pv: [
    {
      id: 'pv1',
      name: 'PV 1',
      collector: 'mv1',
      dc_kwp: 6500,
      loss_factor: 0,
      inverter: { s_rated_kva: 5500, p_max_kw: 5000, v_lv_kv: 0.48 },
      availability: { scenario: 'clear_sky_high', source: 'ac_kw', scale: 1, loop: true },
      transformer: transformer(5500),
    },
  ],
  loads: [{ id: 'load1', name: 'Site load', bus: 'poi', profile: { scenario: 'high_demand', scale: 1, loop: true } }],
  meters: [
    { id: 'm_bess1', name: 'm:bess1', transformer: 'bess1' },
    { id: 'm_bess2', name: 'm:bess2', transformer: 'bess2' },
    { id: 'm_pv1', name: 'm:pv1', transformer: 'pv1' },
  ],
  interfaces: { http: { enabled: true }, modbus: { enabled: true }, dnp3: { enabled: false } },
} as SiteConfig;

// Two collectors with feeder cables, no POI line, a load behind its own transformer.
export const TWO_COLLECTOR_SITE: SiteConfig = {
  ...REFERENCE_SITE,
  poi: {},
  collectors: [
    { id: 'mv1', feeder: { length_km: 0.3, r_ohm_per_km: 0.2, x_ohm_per_km: 0.3 } },
    { id: 'mv2', feeder: { length_km: 0.8, r_ohm_per_km: 0.2, x_ohm_per_km: 0.3 } },
  ],
  bess: [bess('bess1'), { ...bess('bess3'), collector: 'mv2' }],
  loads: [{ ...REFERENCE_SITE.loads![0], transformer: { ...transformer(4000), vn_lv_kv: 0.48 } }],
  meters: [],
} as SiteConfig;
