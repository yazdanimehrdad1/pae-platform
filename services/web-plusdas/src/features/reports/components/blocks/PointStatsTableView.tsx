import { Download } from "lucide-react";
import type { PointStatsTableResult } from "@/api/types/reports";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { downloadFile, fileName, pointStatsCsv } from "../../lib/csv";
import { formatReportTime, formatValue, STAT_LABELS } from "../../lib/format";
import { BlockSection } from "./BlockSection";

export function PointStatsTableView({ block, reportName, timeZone }: {
  block: PointStatsTableResult;
  reportName: string;
  timeZone: string;
}) {
  const stats = block.stats ?? [];
  const bucketed = block.bucket !== "none";
  const download = () => downloadFile(`${fileName(reportName, block.block_id)}.csv`, pointStatsCsv(block, timeZone), "text/csv;charset=utf-8");
  return (
    <BlockSection
      title={block.title}
      error={block.error}
      action={<Button size="sm" variant="outline" className="gap-1.5" onClick={download}><Download aria-hidden className="h-3.5 w-3.5" />CSV</Button>}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Point</TableHead>
            <TableHead>Device</TableHead>
            {bucketed && <TableHead>{block.bucket === "hour" ? "Hour" : "Day"}</TableHead>}
            {stats.map(stat => <TableHead key={stat} className="text-right">{STAT_LABELS[stat]}</TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {(block.rows ?? []).map((row, index) => (
            <TableRow key={`${row.point_id}-${row.bucket_start ?? "all"}-${index}`}>
              <TableCell className="font-medium">{row.point_name}</TableCell>
              <TableCell>{row.device_name}</TableCell>
              {bucketed && <TableCell>{row.bucket_start ? formatReportTime(row.bucket_start, timeZone) : "—"}</TableCell>}
              {stats.map(stat => (
                <TableCell key={stat} className="text-right tabular-nums">
                  {formatValue(row.values?.[stat], stat === "count" ? null : row.unit)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </BlockSection>
  );
}
