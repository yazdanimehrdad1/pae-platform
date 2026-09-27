import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { usePointSeries } from "../hooks/useAlarmsData";
import { formatSiteTime } from "../lib/siteTime";
import { TREND_RANGES, type TrendRange } from "../lib/trendRange";
import type { Point, Severity, ThresholdRule } from "../types";

const LIMIT_COLOR: Record<Severity, string> = {
  fault: "hsl(var(--alarm-fault))",
  warning: "hsl(var(--alarm-warning))",
};

/** A numeric point over the chosen range, with each rule's limit as a dashed line. */
export function TrendChart({ point, limits, now, timeZone, range, onRangeChange }: {
  point: Point;
  limits: ThresholdRule[];
  now: number;
  timeZone: string;
  range: TrendRange;
  onRangeChange: (range: TrendRange) => void;
}) {
  const rangeMs = TREND_RANGES.find(option => option.value === range)!.ms;
  const { data: samples = [], isLoading } = usePointSeries(point.id, now - rangeMs, now);
  const withDate = rangeMs > 24 * 3_600_000;
  const values = samples.map(sample => sample.v);
  const limitValues = limits.map(limit => limit.threshold);
  const domain = values.length
    ? [Math.min(...values, ...limitValues), Math.max(...values, ...limitValues)]
    : ["auto", "auto"];
  const pad = typeof domain[0] === "number" ? ((domain[1] as number) - domain[0]) * 0.1 || 1 : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">
          {point.name} <span className="font-normal text-muted-foreground">({point.unit})</span>
        </h3>
        <ToggleGroup type="single" size="sm" value={range} onValueChange={value => value && onRangeChange(value as TrendRange)}
          aria-label="Trend time range">
          {TREND_RANGES.map(option => (
            <ToggleGroupItem key={option.value} value={option.value} className="h-7 px-2 text-xs">{option.label}</ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <div className="h-56 rounded-md border border-border bg-background p-2" aria-busy={isLoading}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={samples} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="t" type="number" scale="time" domain={[now - rangeMs, now]}
              tickFormatter={t => formatSiteTime(t, timeZone, { withDate }).replace(/:\d\d(?= )/, "")}
              stroke="hsl(var(--muted-foreground))" fontSize={11} minTickGap={48} />
            <YAxis domain={typeof domain[0] === "number" ? [(domain[0] as number) - pad, (domain[1] as number) + pad] : domain}
              stroke="hsl(var(--muted-foreground))" fontSize={11} width={56}
              tickFormatter={value => Number(value).toFixed(point.unit === "MW" || point.unit === "Hz" ? 2 : 0)} />
            <Tooltip
              labelFormatter={t => formatSiteTime(Number(t), timeZone, { withDate: true })}
              formatter={value => [`${value} ${point.unit}`, point.name]}
              contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
            />
            {limits.map(limit => (
              <ReferenceLine key={limit.id} y={limit.threshold} stroke={LIMIT_COLOR[limit.severity]} strokeDasharray="6 4"
                label={{ value: `${limit.severity === "fault" ? "Fault" : "Warning"} ${limit.operator} ${limit.threshold} ${point.unit}`,
                  position: "insideTopRight", fill: LIMIT_COLOR[limit.severity], fontSize: 11 }} />
            ))}
            <Line type="monotone" dataKey="v" stroke="hsl(var(--foreground))" strokeOpacity={0.8} dot={false}
              strokeWidth={1.5} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
