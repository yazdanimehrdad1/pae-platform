import { Fragment, useMemo } from "react";
import { Camera } from "lucide-react";
import { getErrorMessage } from "@/api/client";
import type { DevicePointsEntry, PointGroup } from "@/api/types/devices";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReadingsSnapshot } from "../hooks/useReadingsSnapshot";
import { buildReadingsTable, formatReading, SNAPSHOT_READINGS } from "../lib/readingsSnapshot";

const GROUP_LABEL: Record<PointGroup, string> = { standardized: "Standardized", virtual: "Virtual", native: "Native" };
// Point, Register, Type, Size, Scale and Unit come before the reading columns.
const DETAIL_COLUMNS = 6;

const timeOfDay = (time: string | number) =>
  new Date(time).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

/** Every point of a device with its last readings, one column per poll; refreshed only by "Take snapshot". */
export function DeviceReadingsSnapshot({ siteId, device }: { siteId: string; device: DevicePointsEntry }) {
  const { data, error, isLoading, isFetching, dataUpdatedAt, refetch } = useReadingsSnapshot(siteId, device.deviceId);
  const table = useMemo(() => (data ? buildReadingsTable(device, data) : null), [data, device]);

  return (
    <section aria-labelledby="readings-snapshot-heading" className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="readings-snapshot-heading" className="text-lg font-semibold">{device.deviceName}</h2>
          <p className="text-sm text-muted-foreground">
            {device.points.length} points · last {SNAPSHOT_READINGS} readings per point, newest on the left
            {dataUpdatedAt > 0 && <> · snapshot taken {timeOfDay(dataUpdatedAt)}</>}
          </p>
        </div>
        <Button variant="outline" size="sm" className="gap-2" onClick={() => refetch()} disabled={isFetching}>
          <Camera className={`h-4 w-4 ${isFetching ? "animate-pulse" : ""}`} />
          {isFetching ? "Taking snapshot…" : "Take snapshot"}
        </Button>
      </header>

      {error ? (
        <p role="alert" className="text-sm text-destructive">Snapshot failed: {getErrorMessage(error)}</p>
      ) : isLoading || !table ? (
        <p className="text-sm text-muted-foreground">Taking snapshot…</p>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-md border border-border">
          <Table>
            <TableHeader className="sticky top-0 z-20 bg-card">
              <TableRow>
                <TableHead className="sticky left-0 z-30 min-w-56 bg-card">Point</TableHead>
                <TableHead className="whitespace-nowrap">Register</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead className="text-right">Scale</TableHead>
                <TableHead>Unit</TableHead>
                {table.columns.map(column => (
                  <TableHead key={column.key} className="whitespace-nowrap text-right tabular-nums" title={column.time}>
                    {timeOfDay(column.time)}
                  </TableHead>
                ))}
                {table.columns.length === 0 && <TableHead>No readings stored yet</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {table.groups.map(({ group, rows }) => (
                <Fragment key={group}>
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableCell colSpan={DETAIL_COLUMNS + Math.max(table.columns.length, 1)}
                      className="sticky left-0 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {GROUP_LABEL[group]} ({rows.length})
                    </TableCell>
                  </TableRow>
                  {rows.map(({ point, cells }) => (
                    <TableRow key={point.id}>
                      <TableCell className="sticky left-0 z-10 bg-card font-medium">{point.name}</TableCell>
                      {/* Only native points are read from a register; the others carry a placeholder address. */}
                      <TableCell className="whitespace-nowrap tabular-nums text-muted-foreground">
                        {point.category === "NATIVE"
                          ? <>{point.address}{point.poll_kind && <span className="ml-1 text-xs">{point.poll_kind}</span>}</>
                          : "—"}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{point.data_type}</TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">{point.size}</TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">{point.scale_factor ?? "—"}</TableCell>
                      <TableCell className="text-muted-foreground">{point.unit || "—"}</TableCell>
                      {cells.map((value, index) => {
                        const { text, title } = formatReading(point, value);
                        return (
                          <TableCell key={table.columns[index].key} title={title}
                            className={`whitespace-nowrap text-right tabular-nums ${value === null ? "text-muted-foreground" : ""}`}>
                            {text}
                          </TableCell>
                        );
                      })}
                      {table.columns.length === 0 && <TableCell />}
                    </TableRow>
                  ))}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
