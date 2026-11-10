// Checks what the AI got from a series site function against backend-ot's untouched result (both
// come back from the admin test-run). For display only; the gateway does the real work.
// - every reading: the AI's `start` + `offsets_s` (whole seconds) and `values` (3 decimals) must
//   give back each backend-ot reading in the window, in order;
// - the default: each row must be backend-ot's first reading of its interval, same time and value.

export interface SeriesCheck {
  /** Where the series is in the result, e.g. "series" or "series[1]". */
  path: string;
  ok: boolean;
  summary: string;
  /** Up to MAX_SHOWN rows that differ. */
  differences: string[];
}

interface BackendReading {
  time: string;
  ms: number;
  value: number;
}

const MAX_SHOWN = 5;
const TIME_TOLERANCE_MS = 1000; // offsets are rounded to whole seconds
const VALUE_TOLERANCE = 0.0006; // values are rounded to 3 decimals

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** backend-ot's readings in the window, oldest first; valueless samples (gap markers) skipped. */
function backendReadings(samples: unknown[], startMs: number, endMs: number): BackendReading[] {
  const readings: BackendReading[] = [];
  for (const sample of samples) {
    if (!isRecord(sample) || typeof sample.time !== 'string' || !isNumber(sample.value)) continue;
    const ms = Date.parse(sample.time);
    if (Number.isNaN(ms) || ms < startMs || ms > endMs) continue;
    readings.push({ time: sample.time, ms, value: sample.value });
  }
  return readings.sort((first, second) => first.ms - second.ms);
}

function checkEveryReading(path: string, compact: Record<string, unknown>, readings: BackendReading[]): SeriesCheck {
  const startMs = typeof compact.start === 'string' ? Date.parse(compact.start) : NaN;
  const offsets = Array.isArray(compact.offsets_s) ? compact.offsets_s : [];
  const values = Array.isArray(compact.values) ? compact.values : [];
  const differences: string[] = [];
  let matching = 0;
  const count = Math.max(readings.length, values.length);
  for (let index = 0; index < count; index += 1) {
    const reading = readings[index];
    const offset = offsets[index];
    const value = values[index];
    const aiMs = isNumber(offset) ? startMs + offset * 1000 : NaN;
    if (reading && isNumber(value) && Math.abs(aiMs - reading.ms) <= TIME_TOLERANCE_MS && Math.abs(value - reading.value) <= VALUE_TOLERANCE) {
      matching += 1;
    } else if (differences.length < MAX_SHOWN) {
      const aiText = Number.isNaN(aiMs) ? 'nothing' : `${new Date(aiMs).toISOString()} = ${String(value)}`;
      differences.push(`row ${index + 1}: AI ${aiText}, backend-ot ${reading ? `${reading.time} = ${reading.value}` : 'nothing'}`);
    }
  }
  const ok = matching === readings.length && values.length === readings.length;
  return { path, ok, summary: `${matching} of ${readings.length} readings match backend-ot`, differences };
}

function checkFirstPerInterval(path: string, rows: unknown[], minutes: number, readings: BackendReading[]): SeriesCheck {
  const intervalMs = minutes * 60_000;
  const expected: BackendReading[] = [];
  let lastInterval: number | null = null;
  for (const reading of readings) {
    const interval = Math.floor(reading.ms / intervalMs);
    if (interval !== lastInterval) expected.push(reading);
    lastInterval = interval;
  }
  const differences: string[] = [];
  let matching = 0;
  const count = Math.max(expected.length, rows.length);
  for (let index = 0; index < count; index += 1) {
    const want = expected[index];
    const row = rows[index];
    const got = isRecord(row) ? row : null;
    if (want && got && got.time === want.time && got.value === want.value) {
      matching += 1;
    } else if (differences.length < MAX_SHOWN) {
      const gotText = got ? `${String(got.time)} = ${String(got.value)}` : 'nothing';
      differences.push(`row ${index + 1}: AI ${gotText}, backend-ot ${want ? `${want.time} = ${want.value}` : 'nothing'}`);
    }
  }
  const ok = matching === expected.length && rows.length === expected.length;
  return {
    path,
    ok,
    summary: `${matching} of ${expected.length} rows are backend-ot's first reading of each ${minutes} min (from ${readings.length} readings)`,
    differences,
  };
}

/** One check per series found in both results. `start` / `end` are the run's window. */
export function checkAgainstBackendOt(forAi: unknown, backendOt: unknown, start: string, end: string): SeriesCheck[] {
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  const checks: SeriesCheck[] = [];

  function walk(ai: unknown, original: unknown, path: string): void {
    if (Array.isArray(ai) && Array.isArray(original)) {
      ai.forEach((entry, index) => walk(entry, original[index], `${path}[${index}]`));
      return;
    }
    if (!isRecord(ai) || !isRecord(original)) return;
    if (typeof ai.resolution === 'string' && Array.isArray(original.timeseries)) {
      const readings = backendReadings(original.timeseries, startMs, endMs);
      const interval = /every (\d+) min/.exec(ai.resolution);
      if (isRecord(ai.timeseries)) checks.push(checkEveryReading(path, ai.timeseries, readings));
      else if (interval && Array.isArray(ai.timeseries)) {
        checks.push(checkFirstPerInterval(path, ai.timeseries, Number(interval[1]), readings));
      }
      return;
    }
    for (const [key, entry] of Object.entries(ai)) walk(entry, original[key], path ? `${path}.${key}` : key);
  }

  walk(forAi, backendOt, '');
  return checks;
}
