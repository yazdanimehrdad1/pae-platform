// System alarms mock: every point's value as a deterministic function of time (a daily cycle,
// seeded noise and scripted episodes), so the rule engine derives the spec's alarms instead of
// them being hard-coded. Episodes are placed relative to ANCHOR (page load, whole minute).
import type { PollSample } from '@/features/alarms/types';

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export const ANCHOR = Math.floor(Date.now() / MINUTE) * MINUTE;

/** Deterministic noise in [-1, 1] for a seed and a 10 s bucket of time. */
function noise(seed: number, t: number): number {
  let x = (seed * 374761393 + Math.floor(t / 10_000) * 668265263) | 0;
  x = Math.imul(x ^ (x >>> 13), 1274126177);
  x ^= x >>> 16;
  return ((x >>> 0) / 4294967295) * 2 - 1;
}

/** −1 … 1 over a day, peaking mid-afternoon (UTC). */
const daily = (t: number) => Math.sin((2 * Math.PI * (((t / HOUR) % 24) - 9)) / 24);

const within = (t: number, from: number, to = Infinity) => t >= from && t < to;

const topOilT1 = (t: number) => {
  if (within(t, ANCHOR - 40 * MINUTE)) return 87 + 0.3 * noise(1, t);                     // active warning
  if (within(t, ANCHOR - 3 * DAY, ANCHOR - 3 * DAY + 2 * HOUR)) return 88 + 0.5 * noise(1, t); // history
  return 70 + 4 * daily(t) + 0.8 * noise(1, t);
};

const loadF1 = (t: number) => {
  if (within(t, ANCHOR - 25 * MINUTE)) return 92 + 0.4 * noise(2, t);                       // active warning
  if (within(t, ANCHOR - 2 * DAY, ANCHOR - 2 * DAY + 30 * MINUTE)) return 93 + 0.5 * noise(2, t); // history
  return 72 + 8 * daily(t) + 1.5 * noise(2, t);
};

const currentBP2 = (t: number) => {
  if (within(t, ANCHOR - 8 * MINUTE)) return 688 + 4 * noise(3, t);                          // active fault
  if (within(t, ANCHOR - 6 * DAY, ANCHOR - 6 * DAY + 3 * MINUTE)) return 640 + 5 * noise(3, t); // history
  return 420 + 40 * daily(t) + 8 * noise(3, t);
};

const siteImport = (t: number) => {
  if (within(t, ANCHOR - 60 * MINUTE)) return 4.7 + 0.03 * noise(4, t);                     // active warning (15 min delay)
  return 3.6 + 0.4 * daily(t) + 0.05 * noise(4, t);
};

const frequencyG1 = (t: number) => {
  if (within(t, ANCHOR - 5 * DAY, ANCHOR - 5 * DAY + 2 * MINUTE)) return 59.3 + 0.02 * noise(5, t); // history
  return 60 + 0.02 * noise(5, t);
};

const phaseCurrent = (seed: number, base: number) => (t: number) => base + 40 * daily(t) + 8 * noise(seed, t);

/** Value of every point at time t. Discrete points return their state code. */
export const SIGNALS: Record<string, (t: number) => number> = {
  't1.top_oil_temp': topOilT1,
  't1.winding_temp': t => topOilT1(t) + 8 + 0.5 * noise(11, t),
  't1.load': t => 55 + 10 * daily(t) + noise(12, t),
  't2.top_oil_temp': t => 66 + 4 * daily(t) + 0.8 * noise(13, t),
  't2.winding_temp': t => 73 + 4 * daily(t) + 0.8 * noise(14, t),
  't2.load': t => 50 + 10 * daily(t) + noise(15, t),
  'g1.active_power': t => 1.2 + 0.2 * daily(t) + 0.02 * noise(16, t),
  'g1.frequency': frequencyG1,
  'g1.breaker': () => 1,
  'f1.load': loadF1,
  'f1.current': t => loadF1(t) * 4.2,
  'f1.breaker': () => 1,
  'p1.current_a': phaseCurrent(21, 410),
  'p1.current_b': phaseCurrent(22, 405),
  'p1.current_c': phaseCurrent(23, 412),
  'p2.current_a': phaseCurrent(24, 420),
  'p2.current_b': currentBP2,
  'p2.current_c': phaseCurrent(26, 418),
  'p2.trip': () => 0,
  's1.position': () => 1,
  's1.position_mismatch': t => (within(t, ANCHOR - 2 * HOUR, ANCHOR - 2 * HOUR + 8 * MINUTE) ? 1 : 0),
  's2.position': () => 0,
  'site.import': siteImport,
};

// T2 stops answering for a while: last good poll 51 min before ANCHOR, next one 36 min before,
// so its 60 s comms-stale rule is active from 50 to 36 min before ANCHOR (14 min).
const T2_GAP = { lastOk: ANCHOR - 51 * MINUTE, nextOk: ANCHOR - 36 * MINUTE };

/** Whether a device's poll at time t succeeded. */
export function pollSucceeded(deviceId: string, t: number): boolean {
  return !(deviceId === 't2' && t > T2_GAP.lastOk && t < T2_GAP.nextOk);
}

/** One poll per minute on the minute grid, over [from, to]. */
export function pollsBetween(deviceId: string, from: number, to: number): PollSample[] {
  const polls: PollSample[] = [];
  for (let t = Math.ceil(from / MINUTE) * MINUTE; t <= to; t += MINUTE) polls.push({ t, ok: pollSucceeded(deviceId, t) });
  return polls;
}

export { MINUTE, HOUR, DAY };
