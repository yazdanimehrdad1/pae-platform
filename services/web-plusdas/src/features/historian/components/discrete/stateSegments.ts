import type { ChartRow } from "../../types";

// Runs of one state for the state-lanes renderer: each sample holds until the next one, the last
// holds to the end of the domain, equal neighbours merge, and everything is clipped to the domain.
export interface StateSegment {
  start: number;
  end: number;
  value: number;
}

export function toStateSegments(rows: ChartRow[], key: string, [domainStart, domainEnd]: [number, number]): StateSegment[] {
  const samples = rows.filter(row => row[key] != null);
  const segments: StateSegment[] = [];
  samples.forEach((row, index) => {
    const value = Math.round(row[key]);
    const start = row.timestamp;
    const end = samples[index + 1]?.timestamp ?? Math.max(domainEnd, start);
    const previous = segments[segments.length - 1];
    if (previous && previous.value === value) previous.end = end;
    else segments.push({ start, end, value });
  });
  return segments
    .filter(segment => segment.end > domainStart && segment.start < domainEnd)
    .map(segment => ({ ...segment, start: Math.max(segment.start, domainStart), end: Math.min(segment.end, domainEnd) }));
}
