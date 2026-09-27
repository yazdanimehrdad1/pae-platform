import type { KeyboardEvent } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatLimit, formatPointNumber } from "../lib/alarmModel";
import { SEVERITY } from "../lib/severity";
import type { Point, Severity, ThresholdRule } from "../types";
import { SeverityIndicator } from "./SeverityIndicator";

/** A device's points. A value is colored only while it violates a rule; numeric rows open the trend. */
export function PointsTable({ points, limitsByPoint, violationByPoint, selectedPointId, onSelectPoint }: {
  points: Point[];
  limitsByPoint: Map<string, ThresholdRule[]>;
  violationByPoint: Map<string, Severity>;
  selectedPointId: string | null;
  onSelectPoint: (pointId: string) => void;
}) {
  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, point: Point) => {
    if (point.kind === "numeric" && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      onSelectPoint(point.id);
    }
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-24">Register</TableHead>
          <TableHead>Point</TableHead>
          <TableHead className="text-right">Value</TableHead>
          <TableHead className="w-16">Unit</TableHead>
          <TableHead>Limit</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {points.map(point => {
          const violation = violationByPoint.get(point.id);
          const numeric = point.kind === "numeric";
          const limits = limitsByPoint.get(point.id) ?? [];
          return (
            <TableRow
              key={point.id}
              tabIndex={numeric ? 0 : undefined}
              aria-selected={numeric ? point.id === selectedPointId : undefined}
              onClick={numeric ? () => onSelectPoint(point.id) : undefined}
              onKeyDown={event => onKeyDown(event, point)}
              className={cn(
                numeric ? "cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring" : "cursor-default",
                point.id === selectedPointId && "bg-muted",
              )}
            >
              <TableCell className="tabular-nums text-muted-foreground">{point.register ?? "—"}</TableCell>
              <TableCell>{point.name}</TableCell>
              <TableCell className={cn("text-right tabular-nums", violation && ["font-semibold", SEVERITY[violation].textClass])}>
                <span className="inline-flex items-center justify-end gap-1.5">
                  {violation && <SeverityIndicator severity={violation} showLabel={false} />}
                  {formatPointNumber(point)}
                </span>
              </TableCell>
              <TableCell className="text-muted-foreground">{point.kind === "discrete" ? "—" : point.unit}</TableCell>
              <TableCell className="text-muted-foreground">
                {limits.length ? limits.map(limit => formatLimit(limit, point)).join(", ") : "—"}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
