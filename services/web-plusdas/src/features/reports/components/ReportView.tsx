import type { ReportBlockResult, ReportSnapshot } from "@/api/types/reports";
import { formatReportTime, formatWindow } from "../lib/format";
import { AlarmEventsTableView } from "./blocks/AlarmEventsTableView";
import { ChartBlockView } from "./blocks/ChartBlockView";
import { KpiBlockView } from "./blocks/KpiBlockView";
import { PointStatsTableView } from "./blocks/PointStatsTableView";
import { TextBlockView } from "./blocks/TextBlockView";

/** A generated report, rendered only from its stored snapshot (nothing is re-read). Times show in
 * `timeZone`: the site zone it was generated in, or the user's own. */
export function ReportView({ name, snapshot, timeZone }: { name: string; snapshot: ReportSnapshot; timeZone: string }) {
  return (
    <article className="space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{name}</h1>
        <p className="text-sm text-muted-foreground">
          {snapshot.site_name} · {formatWindow(snapshot.window_start, snapshot.window_end, timeZone)} ({timeZone})
          {timeZone !== snapshot.timezone && ` · generated in site time ${snapshot.timezone}`}
        </p>
        <p className="text-xs text-muted-foreground">Generated {formatReportTime(snapshot.generated_at, timeZone)}</p>
      </header>
      {(snapshot.blocks ?? []).map(block => (
        <BlockView key={block.block_id} block={block} snapshot={snapshot} reportName={name} timeZone={timeZone} />
      ))}
    </article>
  );
}

function BlockView({ block, snapshot, reportName, timeZone }: { block: ReportBlockResult; snapshot: ReportSnapshot; reportName: string; timeZone: string }) {
  switch (block.kind) {
    case "text":
      return <TextBlockView block={block} />;
    case "kpi":
      return <KpiBlockView block={block} />;
    case "chart":
      return <ChartBlockView block={block} windowStart={snapshot.window_start} windowEnd={snapshot.window_end} timeZone={timeZone} />;
    case "point_stats_table":
      return <PointStatsTableView block={block} reportName={reportName} timeZone={timeZone} />;
    case "alarm_events_table":
      return <AlarmEventsTableView block={block} reportName={reportName} timeZone={timeZone} />;
  }
}
