import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartBlockResult } from "@/api/types/reports";
import { SERIES_COLORS, seriesLabel, toBarRows, toSamples } from "../../lib/chartData";
import { formatReportTime, formatValue } from "../../lib/format";
import { BlockSection } from "./BlockSection";

const CHART_HEIGHT = 280;

/** The stored series as they were sampled when the report was generated. Lines break at gaps;
 * each series keeps its own sample times. */
export function ChartBlockView({ block, windowStart, windowEnd, timeZone }: {
  block: ChartBlockResult;
  windowStart: string;
  windowEnd: string;
  timeZone: string;
}) {
  const seriesList = block.series ?? [];
  const domain: [number, number] = [Date.parse(windowStart), Date.parse(windowEnd)];
  const hasSamples = seriesList.some(series => (series.timeseries ?? []).length > 0);
  const axis = (
    <XAxis
      dataKey="time" type="number" scale="time" domain={domain} allowDuplicatedCategory={false}
      tickFormatter={time => formatReportTime(time, timeZone)} tick={{ fontSize: 11 }} minTickGap={48}
    />
  );
  const tooltip = (
    <Tooltip
      labelFormatter={time => formatReportTime(Number(time), timeZone)}
      formatter={(value: number) => formatValue(value)}
    />
  );

  return (
    <BlockSection title={block.title} error={block.error}>
      {!hasSamples ? (
        <p className="text-sm text-muted-foreground">No readings in this period.</p>
      ) : (
        <div style={{ height: CHART_HEIGHT }} className="w-full">
          <ResponsiveContainer width="100%" height="100%">
            {block.style === "bar" ? (
              <BarChart data={toBarRows(seriesList)}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                {axis}
                <YAxis tick={{ fontSize: 11 }} width={64} />
                {tooltip}
                <Legend />
                {seriesList.map((series, index) => (
                  <Bar key={`${series.id}-${index}`} dataKey={`s${index}`} name={seriesLabel(series)} fill={SERIES_COLORS[index % SERIES_COLORS.length]} isAnimationActive={false} />
                ))}
              </BarChart>
            ) : (
              <LineChart>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                {axis}
                <YAxis tick={{ fontSize: 11 }} width={64} />
                {tooltip}
                <Legend />
                {seriesList.map((series, index) => (
                  <Line
                    key={`${series.id}-${index}`}
                    data={toSamples(series)}
                    dataKey="value"
                    name={seriesLabel(series)}
                    type={block.style === "step" ? "stepAfter" : "linear"}
                    stroke={SERIES_COLORS[index % SERIES_COLORS.length]}
                    dot={false}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </BlockSection>
  );
}
