import type { CommsStaleRule, Operator, PollSample, Sample, ThresholdRule } from "../types";

/** One alarm occurrence: raised at a time, cleared at a later one (null while still active). */
export interface AlarmInterval {
  raisedAt: number;
  clearedAt: number | null;
  valueAtRaise: number | null;
}

export function compare(value: number, operator: Operator, threshold: number): boolean {
  switch (operator) {
    case '>': return value > threshold;
    case '<': return value < threshold;
    case '>=': return value >= threshold;
    case '<=': return value <= threshold;
    case '=': return value === threshold;
    case '!=': return value !== threshold;
  }
}

/**
 * Whether an active alarm may clear: the value must move past the threshold by the deadband, on
 * the normal side (hysteresis), so a value hovering at the limit doesn't chatter. `=` and `!=`
 * have no side and clear as soon as the condition is false.
 */
export function isClear(value: number, rule: Pick<ThresholdRule, 'operator' | 'threshold' | 'deadband'>): boolean {
  const { operator, threshold, deadband } = rule;
  switch (operator) {
    case '>':
    case '>=': return value < threshold - deadband;
    case '<':
    case '<=': return value > threshold + deadband;
    case '=':
    case '!=': return !compare(value, operator, threshold);
  }
}

/**
 * Replays time-ordered samples against a threshold rule. An alarm raises once the condition has
 * held continuously for delaySec (at the first sample that completes the delay) and clears at the
 * first sample past threshold ± deadband.
 */
export function evaluateThreshold(samples: Sample[], rule: ThresholdRule): AlarmInterval[] {
  const intervals: AlarmInterval[] = [];
  const delayMs = rule.delaySec * 1000;
  let conditionSince: number | null = null;
  let active: AlarmInterval | null = null;

  for (const { t, v } of samples) {
    if (active) {
      if (isClear(v, rule)) {
        active.clearedAt = t;
        active = null;
        conditionSince = null;
      }
      continue;
    }
    if (!compare(v, rule.operator, rule.threshold)) {
      conditionSince = null;
      continue;
    }
    conditionSince ??= t;
    if (t - conditionSince >= delayMs) {
      active = { raisedAt: t, clearedAt: null, valueAtRaise: v };
      intervals.push(active);
    }
  }
  return intervals;
}

/**
 * Replays a device's polls against a comms-stale rule: stale once more than staleAfterSec pass
 * without a successful poll (raised at lastSuccess + staleAfterSec), cleared by the next success.
 * `now` closes the replay, so a device that stopped answering is stale even with no later polls.
 */
export function evaluateStale(polls: PollSample[], rule: CommsStaleRule, now: number): AlarmInterval[] {
  const intervals: AlarmInterval[] = [];
  const staleMs = rule.staleAfterSec * 1000;
  let lastSuccess: number | null = null;
  let active: AlarmInterval | null = null;

  const checkStale = (t: number) => {
    if (!active && lastSuccess !== null && t - lastSuccess > staleMs) {
      active = { raisedAt: lastSuccess + staleMs, clearedAt: null, valueAtRaise: null };
      intervals.push(active);
    }
  };

  for (const { t, ok } of polls) {
    if (ok) {
      checkStale(t);
      if (active) {
        active.clearedAt = t;
        active = null;
      }
      lastSuccess = t;
    } else {
      checkStale(t);
    }
  }
  checkStale(now);
  return intervals;
}
