// System alarms mock: an in-memory AlarmDataSource. Alarm events are derived by running the real
// rule engine over the mock signals, so a rule created in the UI raises and clears like a live one.
import type { AlarmDataSource, AlarmSnapshot } from '@/features/alarms/data/AlarmDataSource';
import { evaluateStale, evaluateThreshold, type AlarmInterval } from '@/features/alarms/lib/ruleEngine';
import { validateRuleName } from '@/features/alarms/lib/ruleName';
import type { AlarmEvent, AlarmLogEntry, Device, HistoryFilter, Point, Rule, Sample } from '@/features/alarms/types';
import { MOCK_DEVICES, MOCK_POINTS, MOCK_RULES, MOCK_SITE } from './site';
import { DAY, HOUR, MINUTE, SIGNALS, pollsBetween } from './signals';

const HISTORY_WINDOW = 7 * DAY;
const RECENT_WINDOW = 6 * HOUR;
const TICK_MS = 5_000;
/** Devices are polled every 10 s; each one at its own offset in that cycle. */
const POLL_CYCLE_MS = 10_000;

const iso = (t: number) => new Date(t).toISOString();
const round = (value: number) => Math.round(value * 100) / 100;

/** Samples of a point on the whole-minute grid over [from, to] (what the rule engine replays). */
function gridSamples(pointId: string, from: number, to: number): Sample[] {
  const signal = SIGNALS[pointId];
  const samples: Sample[] = [];
  for (let t = Math.ceil(from / MINUTE) * MINUTE; t <= to; t += MINUTE) samples.push({ t, v: signal(t) });
  return samples;
}

export function createMockAlarmSource(options: { now?: () => number; tickMs?: number } = {}): AlarmDataSource {
  const clock = options.now ?? Date.now;
  const tickMs = options.tickMs ?? TICK_MS;
  const pointsById = new Map(MOCK_POINTS.map(point => [point.id, point]));
  let rules: Rule[] = [...MOCK_RULES];
  const listeners = new Set<() => void>();
  let ticker: ReturnType<typeof setInterval> | null = null;
  let now = clock();
  let events: AlarmEvent[] = [];

  function intervalsFor(rule: Rule, from: number, to: number): AlarmInterval[] {
    if (rule.type === 'threshold') {
      return SIGNALS[rule.pointId] ? evaluateThreshold(gridSamples(rule.pointId, from, to), rule) : [];
    }
    return evaluateStale(pollsBetween(rule.deviceId, from, to), rule, to);
  }

  function recompute() {
    events = rules.filter(rule => rule.enabled).flatMap(rule => {
      const deviceId = rule.type === 'threshold' ? pointsById.get(rule.pointId)?.deviceId ?? null : rule.deviceId;
      return intervalsFor(rule, now - HISTORY_WINDOW, now).map((interval): AlarmEvent => {
        const id = `${rule.id}@${interval.raisedAt}`;
        return {
          id,
          ruleId: rule.id,
          deviceId,
          severity: rule.severity,
          raisedAt: iso(interval.raisedAt),
          clearedAt: interval.clearedAt === null ? null : iso(interval.clearedAt),
          valueAtRaise: interval.valueAtRaise === null ? null : round(interval.valueAtRaise),
        };
      });
    });
  }

  function lastPollAt(device: Omit<Device, 'lastPollAt'>): number {
    const offset = (device.unitId * 1_300) % POLL_CYCLE_MS;
    return now - ((now - offset) % POLL_CYCLE_MS);
  }

  function buildLog(recentEvents: AlarmEvent[]): AlarmLogEntry[] {
    const rulesById = new Map(rules.map(rule => [rule.id, rule]));
    const since = now - RECENT_WINDOW;
    const log: AlarmLogEntry[] = [];
    for (const event of recentEvents) {
      const rule = rulesById.get(event.ruleId);
      const name = rule?.name ?? event.ruleId;
      const base = { eventId: event.id, ruleId: event.ruleId, deviceId: event.deviceId, severity: event.severity };
      const add = (kind: AlarmLogEntry['kind'], at: string | null, message: string) => {
        if (at && Date.parse(at) >= since) log.push({ ...base, id: `${event.id}:${kind}`, kind, at, message });
      };
      add('raised', event.raisedAt, rule?.message ?? name);
      add('cleared', event.clearedAt, `${name} cleared`);
    }
    return log.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
  }

  function emitChange() {
    listeners.forEach(listener => listener());
  }

  recompute();

  return {
    async getSnapshot(): Promise<AlarmSnapshot> {
      const devices: Device[] = MOCK_DEVICES.map(device => ({ ...device, lastPollAt: iso(lastPollAt(device)) }));
      const pollAtByDevice = new Map(devices.map(device => [device.id, device.lastPollAt]));
      const points: Point[] = MOCK_POINTS.map(point => ({
        ...point,
        value: round(SIGNALS[point.id](now)),
        quality: 'good',
        updatedAt: point.deviceId ? pollAtByDevice.get(point.deviceId)! : iso(now),
      }));
      const recentEvents = events.filter(event => event.clearedAt === null || Date.parse(event.clearedAt) >= now - RECENT_WINDOW);
      return { site: MOCK_SITE, now, devices, points, rules: [...rules], events: recentEvents, log: buildLog(recentEvents) };
    },

    async getSeries(pointId, from, to) {
      const signal = SIGNALS[pointId];
      if (!signal) return [];
      // About 360 points per chart, never finer than one sample per 10 s.
      const step = Math.max(10_000, Math.ceil((to - from) / 360 / 10_000) * 10_000);
      const samples: Sample[] = [];
      for (let t = Math.ceil(from / step) * step; t <= to; t += step) samples.push({ t, v: round(signal(t)) });
      return samples;
    },

    async queryEvents(filter: HistoryFilter) {
      return events.filter(event => {
        const raised = Date.parse(event.raisedAt);
        const cleared = event.clearedAt ? Date.parse(event.clearedAt) : now;
        if (cleared < filter.from || raised > filter.to) return false;
        if (filter.deviceId && event.deviceId !== filter.deviceId) return false;
        if (filter.severity && event.severity !== filter.severity) return false;
        if (filter.ruleId && event.ruleId !== filter.ruleId) return false;
        return true;
      });
    },

    // Rules only: no notification is really sent. The live backend sends one on each channel
    // switched on in the rule's `notify` (mobile push, email) when the rule raises an alarm.
    async saveRule(rule) {
      // Validated like the backend will: the name is an identifier, unique ignoring case.
      const otherNames = rules.filter(existing => existing.id !== rule.id).map(existing => existing.name);
      const nameError = validateRuleName(rule.name, otherNames);
      if (nameError) throw new Error(`Invalid rule name: ${nameError}`);
      const index = rules.findIndex(existing => existing.id === rule.id);
      rules = index === -1 ? [...rules, rule] : rules.map(existing => (existing.id === rule.id ? rule : existing));
      recompute();
      emitChange();
    },

    subscribe(onChange) {
      listeners.add(onChange);
      ticker ??= setInterval(() => {
        now = clock();
        recompute();
        emitChange();
      }, tickMs);
      return () => {
        listeners.delete(onChange);
        if (listeners.size === 0 && ticker) {
          clearInterval(ticker);
          ticker = null;
        }
      };
    },
  };
}

export const mockAlarmSource = createMockAlarmSource();
