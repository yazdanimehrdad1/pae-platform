import { describe, expect, it } from 'vitest';
import type { AutoDispatchReport } from '@/api/types/powerflow';
import { draftFromReport, isDraftValid, requestFromDraft } from '@/features/simulation/lib/autoDispatchDraft';

// The auto dispatch form: blank fields are left out of the request (they fall back), a BESS
// with nothing set is left out, and what powerflow reports fills the form back in.

const REPORT: AutoDispatchReport = {
  enabled: true,
  power_pct: 40,
  defaults: { soc_low_pct: 20, rest_s: 300 },
  bess_overrides: { bess2: { included: false }, bess1: { start_direction: 'charge', q_kvar: -100 } },
  bess: [],
};

describe('autoDispatchDraft', () => {
  it('round-trips the reported settings into the same request', () => {
    const draft = draftFromReport(REPORT, ['bess1', 'bess2', 'bess3']);
    expect(draft.defaults.values.soc_low_pct).toBe('20');
    expect(draft.defaults.values.soc_high_pct).toBe('');
    expect(draft.bess.bess2.included).toBe(false);
    expect(draft.bess.bess3.included).toBe(true);
    expect(requestFromDraft(draft, true)).toEqual({
      enabled: true,
      power_pct: 40,
      defaults: { soc_low_pct: 20, rest_s: 300 },
      bess: { bess1: { start_direction: 'charge', q_kvar: -100 }, bess2: { included: false } },
    });
  });

  it('starts from the default power and no settings while off', () => {
    const draft = draftFromReport(undefined, ['bess1']);
    expect(requestFromDraft(draft, true)).toEqual({ enabled: true, power_pct: 50, defaults: {}, bess: {} });
  });

  it('rejects a power outside (0, 100] and a field that is not a number', () => {
    const draft = draftFromReport(undefined, ['bess1']);
    expect(isDraftValid(draft)).toBe(true);
    expect(isDraftValid({ ...draft, powerPct: '0' })).toBe(false);
    expect(isDraftValid({ ...draft, powerPct: '101' })).toBe(false);
    const badRest = { ...draft.defaults, values: { ...draft.defaults.values, rest_s: 'abc' } };
    expect(isDraftValid({ ...draft, defaults: badRest })).toBe(false);
  });
});
