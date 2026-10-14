import { Download } from "lucide-react";
import type { AlarmEventsTableResult } from "@/api/types/reports";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SeverityIndicator } from "@/shared/components/SeverityIndicator";
import { formatDuration } from "@/shared/lib/siteTime";
import { alarmEventsCsv, downloadFile, fileName } from "../../lib/csv";
import { formatReportTime, formatValue } from "../../lib/format";
import { BlockSection } from "./BlockSection";

export function AlarmEventsTableView({ block, reportName, timeZone }: {
  block: AlarmEventsTableResult;
  reportName: string;
  timeZone: string;
}) {
  const rows = block.rows ?? [];
  const totalCount = block.total_count ?? rows.length;
  const download = () => downloadFile(`${fileName(reportName, block.block_id)}.csv`, alarmEventsCsv(block, timeZone), "text/csv;charset=utf-8");
  return (
    <BlockSection
      title={block.title}
      error={block.error}
      action={rows.length > 0 && <Button size="sm" variant="outline" className="gap-1.5" onClick={download}><Download aria-hidden className="h-3.5 w-3.5" />CSV</Button>}
    >
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No alarm events in this period.</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Alarm</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Device</TableHead>
                <TableHead>Raised</TableHead>
                <TableHead>Cleared</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead className="text-right">Value</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(row => (
                <TableRow key={row.event_id}>
                  <TableCell className="font-medium" title={row.message}>{row.alarm_name}</TableCell>
                  <TableCell><SeverityIndicator severity={row.severity} /></TableCell>
                  <TableCell>{row.device_name ?? "Site"}</TableCell>
                  <TableCell>{formatReportTime(row.raised_at, timeZone)}</TableCell>
                  <TableCell>{row.cleared_at ? formatReportTime(row.cleared_at, timeZone) : "Active"}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {row.duration_seconds === null || row.duration_seconds === undefined ? "—" : formatDuration(row.duration_seconds * 1000)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatValue(row.value_at_raise)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {totalCount > rows.length && (
            <p className="text-xs text-muted-foreground">Showing the newest {rows.length} of {totalCount} events.</p>
          )}
        </>
      )}
    </BlockSection>
  );
}
