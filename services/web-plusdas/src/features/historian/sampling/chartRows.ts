import type { PointTimeseries } from '@/api/types/historian';
import { decodeBit, parseSelectionId } from '@/shared/lib/discretePoints';
import type { ChartRow } from '../types';
import { ROW_TOLERANCE_MS } from './constants';

// Series by key: a readings response's `readings` (keyed by point id), or a profile function's
// series keyed by its selection id ("fn:...").
export type SeriesByKey = Record<string, PointTimeseries>;

// One sample of one line, keyed by its selection id (as Recharts' dataKey): { timestamp, [id]: value }.
// A null value is a gap marker: the line breaks there (an outage).
export type LinePoint = { timestamp: number } & Record<string, number | null>;

interface Reading {
  timestamp: number;
  key: string;
  value: number;
}

function selectionsByKey(selectionIds: string[]): Map<string, Array<{ selectionId: string; bit?: number }>> {
  const byKey = new Map<string, Array<{ selectionId: string; bit?: number }>>();
  for (const selectionId of selectionIds) {
    const { pointId, bit } = parseSelectionId(selectionId);
    byKey.set(pointId, [...(byKey.get(pointId) ?? []), { selectionId, bit }]);
  }
  return byKey;
}

const valueOf = (value: number, bit: number | undefined) => (bit === undefined ? value : decodeBit(value, bit));

// Merges fetched series into rows for Recharts, one column per selection, each series at its own
// sample times (no resampling): one poll cycle across devices is one row, stamped with its last
// reading's time. A series sampled twice within the tolerance gets two rows, and a series with no
// reading in a row leaves its column empty. Gap markers (null values) are left out. The discrete
// renderers (state lanes, step lines) and the chart's hover positions use these rows.
// A bit selection ("12:bit3") gets that bit (0/1) of point 12's raw value; others get the value.
export function buildChartRows(seriesMaps: SeriesByKey[], selectionIds: string[]): ChartRow[] {
  const byKey = selectionsByKey(selectionIds);

  const readings: Reading[] = [];
  for (const seriesByKey of seriesMaps) {
    for (const [key, series] of Object.entries(seriesByKey)) {
      if (!byKey.has(key)) continue;
      for (const entry of series.timeseries) {
        if (entry.value == null) continue;
        readings.push({ timestamp: new Date(entry.time).getTime(), key, value: entry.value });
      }
    }
  }
  readings.sort((left, right) => left.timestamp - right.timestamp);

  const rows: ChartRow[] = [];
  let row: ChartRow | null = null;
  let rowStart = 0;
  let keysInRow = new Set<string>();
  for (const { timestamp, key, value } of readings) {
    if (!row || timestamp - rowStart >= ROW_TOLERANCE_MS || keysInRow.has(key)) {
      row = { timestamp };
      rows.push(row);
      rowStart = timestamp;
      keysInRow = new Set();
    }
    row.timestamp = timestamp;
    keysInRow.add(key);
    for (const { selectionId, bit } of byKey.get(key)!) row[selectionId] = valueOf(value, bit);
  }
  return rows;
}

// Each selection's own samples, oldest first, for drawing one line per series: every sample it
// received, at its own time, so series that don't share timestamps (plot values) still draw
// continuous lines. Gap markers stay in as null values, so a line breaks only at its own outages.
export function buildLineSeries(seriesMaps: SeriesByKey[], selectionIds: string[]): Record<string, LinePoint[]> {
  const byKey = selectionsByKey(selectionIds);
  const lines: Record<string, LinePoint[]> = Object.fromEntries(selectionIds.map(selectionId => [selectionId, []]));
  for (const seriesByKey of seriesMaps) {
    for (const [key, series] of Object.entries(seriesByKey)) {
      for (const { selectionId, bit } of byKey.get(key) ?? []) {
        for (const entry of series.timeseries) {
          const timestamp = new Date(entry.time).getTime();
          lines[selectionId].push({ timestamp, [selectionId]: entry.value == null ? null : valueOf(entry.value, bit) } as LinePoint);
        }
      }
    }
  }
  for (const points of Object.values(lines)) points.sort((left, right) => left.timestamp - right.timestamp);
  return lines;
}
