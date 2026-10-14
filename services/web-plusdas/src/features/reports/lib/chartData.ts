import type { PointTimeseries } from "@/api/types/reports";

export interface ChartSample {
  time: number;
  value: number | null;
}

/** One series as chart samples (epoch ms), oldest first. A null value is a gap the line breaks at. */
export function toSamples(series: PointTimeseries): ChartSample[] {
  return (series.timeseries ?? []).map(sample => ({ time: Date.parse(sample.time), value: sample.value ?? null }));
}

/** Rows for a bar chart: one per time any series has a sample, a key per series ("s0", "s1"...). */
export function toBarRows(seriesList: PointTimeseries[]): Array<Record<string, number | null>> {
  const rowsByTime = new Map<number, Record<string, number | null>>();
  seriesList.forEach((series, index) => {
    for (const sample of toSamples(series)) {
      const row = rowsByTime.get(sample.time) ?? { time: sample.time };
      row[`s${index}`] = sample.value;
      rowsByTime.set(sample.time, row);
    }
  });
  return [...rowsByTime.values()].sort((first, second) => (first.time as number) - (second.time as number));
}

/** "active_power (kW)". */
export function seriesLabel(series: PointTimeseries): string {
  return series.unit ? `${series.name} (${series.unit})` : series.name;
}

// Distinct hues that read on light and dark backgrounds and in print.
export const SERIES_COLORS = ["#2563eb", "#d97706", "#059669", "#db2777", "#7c3aed", "#0891b2", "#65a30d", "#dc2626"];
