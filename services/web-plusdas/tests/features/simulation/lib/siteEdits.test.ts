import { describe, expect, it } from 'vitest';
import { applySiteEdits, editsFromConfig, hasChanges } from '@/features/simulation/lib/siteEdits';
import { REFERENCE_SITE } from '../fixtures';

describe('site edits', () => {
  it('reads the selection fields from a config', () => {
    const edits = editsFromConfig(REFERENCE_SITE);
    expect(edits.simulation.seed).toBe(42);
    expect(edits.loadProfiles.load1).toEqual({ scenario: 'high_demand', scale: 1 });
    expect(edits.pvProfiles.pv1).toEqual({ scenario: 'clear_sky_high', scale: 1 });
    expect(edits.modbusEnabled).toBe(true);
    expect(hasChanges(REFERENCE_SITE, edits)).toBe(false);
  });

  it('changes only the allowed fields and carries everything else over', () => {
    const edits = editsFromConfig(REFERENCE_SITE);
    edits.simulation.step_s = 2;
    edits.simulation.test_mode = true;
    edits.loadProfiles.load1 = { scenario: 'evening_peak', scale: 0.5 };
    edits.pvProfiles.pv1 = { scenario: 'cloudy', scale: 0.8 };
    edits.modbusEnabled = false;
    expect(hasChanges(REFERENCE_SITE, edits)).toBe(true);

    const saved = applySiteEdits(REFERENCE_SITE, edits);
    expect(saved.simulation?.step_s).toBe(2);
    expect(saved.simulation?.test_mode).toBe(true);
    expect(saved.loads?.[0].profile).toEqual({ scenario: 'evening_peak', scale: 0.5, loop: true });
    expect(saved.pv?.[0].availability).toEqual({ scenario: 'cloudy', scale: 0.8, source: 'ac_kw', loop: true });
    expect(saved.interfaces?.modbus?.enabled).toBe(false);

    // Assets, ratings, topology and meters are untouched.
    expect(saved.bess).toEqual(REFERENCE_SITE.bess);
    expect(saved.grid).toEqual(REFERENCE_SITE.grid);
    expect(saved.poi).toEqual(REFERENCE_SITE.poi);
    expect(saved.collectors).toEqual(REFERENCE_SITE.collectors);
    expect(saved.meters).toEqual(REFERENCE_SITE.meters);
    expect(saved.pv?.[0].inverter).toEqual(REFERENCE_SITE.pv?.[0].inverter);
    // The input isn't mutated.
    expect(REFERENCE_SITE.simulation?.step_s).toBe(1);
  });
});
