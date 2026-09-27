import { describe, expect, it } from 'vitest';
import type { CommsStaleRule, Sample, ThresholdRule } from '../types';
import { compare, evaluateStale, evaluateThreshold, isClear } from './ruleEngine';

const rule = (overrides: Partial<ThresholdRule> = {}): ThresholdRule => ({
  id: 'r1', type: 'threshold', name: 'High temp', pointId: 'p1', operator: '>', threshold: 85,
  delaySec: 0, deadband: 0, severity: 'warning', message: 'High temp', enabled: true, notify: { mobile: true, email: false }, ...overrides,
});

// One sample per second from t = 0 s.
const series = (...values: number[]): Sample[] => values.map((v, i) => ({ t: i * 1000, v }));

describe('compare', () => {
  it.each([
    ['>', 5, 4, true], ['>', 4, 4, false],
    ['<', 3, 4, true], ['<', 4, 4, false],
    ['>=', 4, 4, true], ['<=', 4, 4, true],
    ['=', 1, 1, true], ['=', 0, 1, false],
    ['!=', 0, 1, true], ['!=', 1, 1, false],
  ] as const)('%s: %d vs %d → %s', (operator, value, threshold, expected) => {
    expect(compare(value, operator, threshold)).toBe(expected);
  });
});

describe('isClear (hysteresis)', () => {
  it('clears a high alarm only below threshold − deadband', () => {
    expect(isClear(84, { operator: '>', threshold: 85, deadband: 2 })).toBe(false);
    expect(isClear(82.9, { operator: '>', threshold: 85, deadband: 2 })).toBe(true);
  });

  it('clears a low alarm only above threshold + deadband', () => {
    expect(isClear(11, { operator: '<', threshold: 10, deadband: 2 })).toBe(false);
    expect(isClear(12.1, { operator: '<', threshold: 10, deadband: 2 })).toBe(true);
  });

  it('clears = and != as soon as the condition is false', () => {
    expect(isClear(0, { operator: '=', threshold: 1, deadband: 5 })).toBe(true);
    expect(isClear(1, { operator: '!=', threshold: 0, deadband: 5 })).toBe(false);
  });
});

describe('evaluateThreshold', () => {
  it('raises at the first violating sample when there is no delay', () => {
    expect(evaluateThreshold(series(80, 86, 87), rule())).toEqual([
      { raisedAt: 1000, clearedAt: null, valueAtRaise: 86 },
    ]);
  });

  it('does not raise for a spike shorter than the delay', () => {
    expect(evaluateThreshold(series(80, 90, 90, 80, 90, 80), rule({ delaySec: 2 }))).toEqual([]);
  });

  it('raises once the condition has held for the whole delay', () => {
    expect(evaluateThreshold(series(80, 90, 90, 90, 90), rule({ delaySec: 2 }))).toEqual([
      { raisedAt: 3000, clearedAt: null, valueAtRaise: 90 },
    ]);
  });

  it('stays active inside the deadband and clears past it', () => {
    const intervals = evaluateThreshold(series(90, 84, 83.5, 82, 90), rule({ deadband: 2 }));
    expect(intervals).toEqual([
      { raisedAt: 0, clearedAt: 3000, valueAtRaise: 90 },
      { raisedAt: 4000, clearedAt: null, valueAtRaise: 90 },
    ]);
  });

  it('restarts the delay after the condition drops', () => {
    // Holds 1 s, drops, then holds 2 s: only the second run completes a 2 s delay.
    expect(evaluateThreshold(series(90, 90, 80, 90, 90, 90), rule({ delaySec: 2 }))).toEqual([
      { raisedAt: 5000, clearedAt: null, valueAtRaise: 90 },
    ]);
  });
});

describe('evaluateStale', () => {
  const staleRule: CommsStaleRule = {
    id: 's1', type: 'comms_stale', name: 'Comms stale', deviceId: 'd1', staleAfterSec: 30,
    severity: 'warning', message: 'Comms lost', enabled: true, notify: { mobile: false, email: false },
  };

  it('raises after staleAfterSec without a successful poll and clears on the next success', () => {
    const polls = [
      { t: 0, ok: true }, { t: 10_000, ok: false }, { t: 40_000, ok: false }, { t: 50_000, ok: true },
    ];
    expect(evaluateStale(polls, staleRule, 60_000)).toEqual([
      { raisedAt: 30_000, clearedAt: 50_000, valueAtRaise: null },
    ]);
  });

  it('does not raise for gaps up to staleAfterSec', () => {
    const polls = [{ t: 0, ok: true }, { t: 20_000, ok: false }, { t: 30_000, ok: true }];
    expect(evaluateStale(polls, staleRule, 40_000)).toEqual([]);
  });

  it('is still active at `now` when polling stopped altogether', () => {
    expect(evaluateStale([{ t: 0, ok: true }], staleRule, 45_000)).toEqual([
      { raisedAt: 30_000, clearedAt: null, valueAtRaise: null },
    ]);
  });
});
