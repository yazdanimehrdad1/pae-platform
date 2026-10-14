import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getErrorMessage } from "@/api/client";
import type { DeviceReadings } from "@/api/types/powerflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDeviceHistory, useDevices, useLatestSnapshot, useModbusRegisters } from "../hooks/usePowerflow";
import {
  deviceKey,
  deviceName,
  filterPoints,
  formatReading,
  isTrendable,
  registersByPoint,
  trendRows,
} from "../lib/measurements";

const MAX_TREND_POINTS = 6;
const LINE_COLORS = [
  "hsl(var(--primary))",
  "#10b981",
  "#f59e0b",
  "#0ea5e9",
  "#ef4444",
  "#8b5cf6",
];
const utcTime = (t: number) => new Date(t).toISOString().slice(11, 19);

function DeviceTrend({ device, points }: { device: DeviceReadings; points: string[] }) {
  const history = useDeviceHistory(device, points);
  const rows = useMemo(() => (history.data ? trendRows(history.data) : []), [history.data]);
  const units = new Map(history.data?.points.map((point) => [point.point, point.unit]) ?? []);
  if (history.isError) return <p role="alert" className="text-sm text-destructive">{getErrorMessage(history.error)}</p>;
  return (
    <div className="h-64 rounded-md border border-border bg-background p-2" aria-busy={history.isLoading} data-device-trend>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={utcTime}
            stroke="hsl(var(--muted-foreground))" fontSize={11} minTickGap={48} />
          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} width={72}
            tickFormatter={(value) => String(Number(Number(value).toPrecision(4)))} />
          <Tooltip
            labelFormatter={(t) => `${new Date(Number(t)).toISOString().replace("T", " ").slice(0, 19)} UTC`}
            formatter={(value, name) => [`${value} ${units.get(String(name)) ?? ""}`.trim(), name]}
            contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {points.map((point, index) => (
            <Line key={point} type="stepAfter" dataKey={point} dot={false} isAnimationActive={false}
              stroke={LINE_COLORS[index % LINE_COLORS.length]} strokeWidth={1.5} connectNulls={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function RawSnapshot() {
  const [open, setOpen] = useState(false);
  const snapshot = useLatestSnapshot(open);
  return (
    <div className="space-y-2">
      <Button size="sm" variant="ghost" className="gap-1 px-0" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
        {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Raw snapshot (powerflow's native names: GET /measurements/latest)
      </Button>
      {open && (
        <pre className="max-h-96 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs" data-raw-snapshot>
          {snapshot.isError ? getErrorMessage(snapshot.error) : snapshot.data ? JSON.stringify(snapshot.data, null, 2) : "Loading..."}
        </pre>
      )}
    </div>
  );
}

// The active site's measurements as PAE point-standard devices (the same points and values the
// Modbus server serves, in SI units with labels), a trend of chosen points over the in-memory
// history, and the native snapshot as raw JSON. For quick visualization; polled every few seconds.
export function MeasurementsPanel({ selectedIsActive }: { selectedIsActive: boolean }) {
  const devices = useDevices(selectedIsActive);
  const layout = useModbusRegisters(selectedIsActive);
  const [chosen, setChosen] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [showUnserved, setShowUnserved] = useState(false);
  const [trend, setTrend] = useState<Record<string, string[]>>({}); // device key → points

  if (!selectedIsActive) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Measurements come from the running simulation: activate this site to see them.
        </CardContent>
      </Card>
    );
  }
  if (devices.isLoading) return <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />;
  if (devices.isError || !devices.data) {
    return (
      <p role="alert" className="text-destructive">
        {getErrorMessage(devices.error, "No measurements yet")}: start the simulation (or step it in test mode).
      </p>
    );
  }

  const data = devices.data;
  const device = data.devices.find((item) => deviceKey(item) === chosen) ?? data.devices[0];
  const key = device ? deviceKey(device) : "";
  const trendPoints = trend[key] ?? [];
  const toggleTrend = (point: string, on: boolean) =>
    setTrend((current) => {
      const points = current[key] ?? [];
      const next = on ? [...points, point].slice(0, MAX_TREND_POINTS) : points.filter((item) => item !== point);
      return { ...current, [key]: next };
    });
  const points = device ? filterPoints(device.points, query, showUnserved) : [];
  const registers = registersByPoint(layout.data?.devices.find((item) => deviceKey(item) === key));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[16rem_1fr] gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Devices</CardTitle>
          <CardDescription>The site as PAE point-standard devices.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1 p-2">
          {data.devices.map((item) => (
            <Button
              key={deviceKey(item)}
              variant={deviceKey(item) === key ? "secondary" : "ghost"}
              className="w-full justify-between"
              data-device={deviceKey(item)}
              onClick={() => setChosen(deviceKey(item))}
            >
              <span>{deviceName(item)}</span>
              <span className="text-xs text-muted-foreground">@{item.base}</span>
            </Button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            {device ? deviceName(device) : "No devices"}
            {!data.converged && <Badge variant="destructive">not converged: last good values</Badge>}
          </CardTitle>
          <CardDescription>
            Step {data.step_id} · {new Date(data.sim_time).toISOString().replace("T", " ").slice(0, 19)} UTC · standard
            names, SI units and codes, the same values the Modbus server serves (Modbus rounds them to each register's
            scale). Tick numeric points to trend them.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {device && trendPoints.length > 0 && <DeviceTrend device={device} points={trendPoints} />}
          <div className="flex flex-wrap items-center gap-4">
            <Input className="w-64" placeholder="Filter points" aria-label="Filter points" value={query}
              onChange={(event) => setQuery(event.target.value)} />
            <div className="flex items-center gap-2">
              <Switch id="show_unserved" checked={showUnserved} onCheckedChange={setShowUnserved} />
              <Label htmlFor="show_unserved">Show points the simulator doesn't serve</Label>
            </div>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">Trend</TableHead>
                <TableHead>Point</TableHead>
                <TableHead>Registers</TableHead>
                <TableHead>Label</TableHead>
                <TableHead className="text-right">Value</TableHead>
                <TableHead>Source</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {points.map((point) => (
                <TableRow key={point.point} data-point={point.point}>
                  <TableCell>
                    {isTrendable(point) && (
                      <Checkbox
                        aria-label={`Trend ${point.point}`}
                        checked={trendPoints.includes(point.point)}
                        disabled={!trendPoints.includes(point.point) && trendPoints.length >= MAX_TREND_POINTS}
                        onCheckedChange={(on) => toggleTrend(point.point, on === true)}
                      />
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{point.point}</TableCell>
                  <TableCell className="font-mono text-xs" data-registers>
                    {registers.get(point.point)?.join(", ") ?? "–"}
                  </TableCell>
                  <TableCell className="text-sm">{point.label}</TableCell>
                  <TableCell className="text-right font-mono text-sm" data-value>
                    {formatReading(point)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={point.served === "no" ? "outline" : "secondary"} className="text-xs">
                      {point.served === "no" ? "not served" : point.served}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <RawSnapshot />
        </CardContent>
      </Card>
    </div>
  );
}
