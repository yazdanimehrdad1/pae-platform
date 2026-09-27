export const TREND_RANGES = [
  { value: "1h", label: "1 h", ms: 3_600_000 },
  { value: "6h", label: "6 h", ms: 6 * 3_600_000 },
  { value: "24h", label: "24 h", ms: 24 * 3_600_000 },
  { value: "7d", label: "7 d", ms: 7 * 24 * 3_600_000 },
] as const;

export type TrendRange = (typeof TREND_RANGES)[number]["value"];
