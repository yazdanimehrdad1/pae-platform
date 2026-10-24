import { parseForecastSelectionId, parseFunctionSelectionId } from "@/shared/lib/discretePoints";
import type { LinePoint } from "../sampling/chartRows";

/** The time of the newest device reading among `keys` (null when none has one). It tells whether
 * the data is live, so PV forecasts (which reach into the future) and profile functions (computed,
 * not read from a device) are left out, and so are gap markers (null values: an outage). */
export function latestReadingTime(lines: Record<string, LinePoint[]>, keys: string[]): number | null {
  let latest: number | null = null;
  for (const key of keys) {
    if (parseForecastSelectionId(key) || parseFunctionSelectionId(key)) continue;
    for (const sample of lines[key] ?? []) {
      if (sample[key] == null) continue;
      if (latest === null || sample.timestamp > latest) latest = sample.timestamp;
    }
  }
  return latest;
}
