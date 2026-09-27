import { describe, expect, it } from 'vitest';
import type { AlarmEvent } from '@/features/alarms/types';
import { createMockAlarmSource } from './mockAlarmSource';
import { ANCHOR, HOUR, MINUTE } from './signals';

// The seeded data must produce exactly the spec's alarms, derived by the rule engine.
const source = () => createMockAlarmSource({ now: () => ANCHOR });
const minutesAgo = (at: string) => Math.round((ANCHOR - Date.parse(at)) / MINUTE);

describe('mock alarm source', () => {
  it('has the four active alarms from the spec', async () => {
    const { events } = await source().getSnapshot();
    const active = events.filter(event => event.clearedAt === null);
    const byRule = Object.fromEntries(active.map(event => [event.ruleId, event])) as Record<string, AlarmEvent>;

    expect(Object.keys(byRule).sort()).toEqual(['f1.load.high', 'p2.current_b.high', 'site.import.high', 't1.top_oil_temp.high']);

    expect(byRule['p2.current_b.high']).toMatchObject({ severity: 'fault', deviceId: 'p2' });
    expect(byRule['p2.current_b.high'].valueAtRaise).toBeGreaterThan(680);
    expect(minutesAgo(byRule['p2.current_b.high'].raisedAt)).toBe(8);

    expect(byRule['t1.top_oil_temp.high']).toMatchObject({ severity: 'warning', deviceId: 't1' });
    expect(byRule['site.import.high']).toMatchObject({ severity: 'warning', deviceId: null });
    expect(minutesAgo(byRule['site.import.high'].raisedAt)).toBe(45); // 60 min above 4.5 MW, 15 min delay
    expect(byRule['f1.load.high']).toMatchObject({ severity: 'warning', deviceId: 'f1' });
  });

  it('has the two recently cleared events from the spec', async () => {
    const { events } = await source().getSnapshot();
    const cleared = events.filter(event => event.clearedAt !== null);
    const durations = Object.fromEntries(cleared.map(event => [
      event.ruleId, (Date.parse(event.clearedAt!) - Date.parse(event.raisedAt)) / MINUTE,
    ]));
    expect(durations).toEqual({ 't2.comms_stale': 14, 's1.position_mismatch': 8 });
  });

  it('keeps older episodes for the history query only', async () => {
    const history = await source().queryEvents({ from: ANCHOR - 7 * 24 * HOUR, to: ANCHOR });
    const rules = new Set(history.map(event => event.ruleId));
    expect(rules).toEqual(new Set([
      'p2.current_b.high', 't1.top_oil_temp.high', 'site.import.high', 'f1.load.high',
      't2.comms_stale', 's1.position_mismatch', 'g1.frequency.low',
    ]));
  });

  it('logs every raise and clear of the recent window', async () => {
    const { log } = await source().getSnapshot();
    const t2 = log.filter(entry => entry.ruleId === 't2.comms_stale').map(entry => entry.kind);
    expect(t2).toEqual(['cleared', 'raised']); // newest first
  });

  it("saves a rule's notification channels without changing its alarms", async () => {
    const alarms = source();
    const before = await alarms.getSnapshot();
    const rule = before.rules.find(existing => existing.id === 'p2.current_b.high')!;
    expect(rule.notify).toEqual({ mobile: true, email: true });

    await alarms.saveRule({ ...rule, notify: { mobile: false, email: true } });

    const after = await alarms.getSnapshot();
    expect(after.rules.find(existing => existing.id === rule.id)!.notify).toEqual({ mobile: false, email: true });
    expect(after.events.filter(event => event.clearedAt === null)).toHaveLength(4);
  });

  it('rejects a rule with an invalid or duplicate name', async () => {
    const alarms = source();
    const rule = (await alarms.getSnapshot()).rules.find(existing => existing.id === 'f1.load.high')!;

    await expect(alarms.saveRule({ ...rule, id: 'new', name: 'f1 load' })).rejects.toThrow(/a space is not allowed/);
    await expect(alarms.saveRule({ ...rule, id: 'new', name: 'F1_LOAD_HIGH' })).rejects.toThrow(/already exists/);
    // Saving a rule under its own name (e.g. toggling a switch) is fine.
    await expect(alarms.saveRule({ ...rule, notify: { mobile: true, email: true } })).resolves.toBeUndefined();
  });

  it('evaluates a new rule against the mock history right away', async () => {
    const alarms = source();
    await alarms.saveRule({
      id: 'custom', type: 'threshold', name: 'p2_phase_a_high', pointId: 'p2.current_a', operator: '>',
      threshold: 100, delaySec: 0, deadband: 0, severity: 'warning', message: 'P2 phase A above 100 A', enabled: true,
      notify: { mobile: true, email: false },
    });
    const { events } = await alarms.getSnapshot();
    expect(events.find(event => event.ruleId === 'custom')).toMatchObject({ clearedAt: null });
  });
});
