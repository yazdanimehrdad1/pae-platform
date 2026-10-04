import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ModbusDevice } from "@/api/types/powerflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { powerflowKeys } from "../hooks/usePowerflow";

const SUPPORT_STYLE: Record<string, string> = {
  yes: "bg-success/20 text-success border-success",
  calc: "bg-primary/20 text-primary border-primary",
  no: "text-muted-foreground",
};

function DeviceRegisters({ device, servedOnly }: { device: ModbusDevice; servedOnly: boolean }) {
  const registers = servedOnly ? device.registers.filter((register) => register.powerflow_server !== "no") : device.registers;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Address</TableHead>
          <TableHead>Point</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Scale</TableHead>
          <TableHead>Unit</TableHead>
          <TableHead>powerflow</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {registers.map((register) => (
          <TableRow key={register.address}>
            <TableCell className="font-mono">{register.address}</TableCell>
            <TableCell>{register.point}</TableCell>
            <TableCell>{register.data_type}</TableCell>
            <TableCell>{register.scale}</TableCell>
            <TableCell>{register.unit}</TableCell>
            <TableCell>
              <Badge variant="outline" className={SUPPORT_STYLE[register.powerflow_server]}>
                {register.powerflow_server}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function AggregatorLayout() {
  const layout = useQuery({ queryKey: powerflowKeys.modbusRegisters, queryFn: powerflowApi.getModbusRegisters, retry: false });
  const [open, setOpen] = useState<string | null>(null);
  const [servedOnly, setServedOnly] = useState(true);

  if (layout.isLoading) return <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />;
  if (layout.isError) return <p role="alert" className="text-destructive">{getErrorMessage(layout.error)}</p>;
  const data = layout.data;
  if (!data) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Modbus server{" "}
          <Badge variant="outline" className={data.enabled ? SUPPORT_STYLE.yes : ""}>
            {data.enabled ? "enabled" : "disabled"}
          </Badge>
        </CardTitle>
        <CardDescription>
          The active site as one aggregator: port {data.port} in the container (1502 on the dev host), unit id {data.unit_id},
          zero-based addresses, holding = input, read-only. Each device owns 100 registers.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2">
          <Switch id="served-only" checked={servedOnly} onCheckedChange={setServedOnly} />
          <Label htmlFor="served-only">Only points powerflow serves (yes / calc)</Label>
        </div>
        {data.devices.map((device) => {
          const key = `${device.kind}.${device.asset_id}`;
          const isOpen = open === key;
          return (
            <div key={key} className="border border-border rounded-md">
              <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => setOpen(isOpen ? null : key)}>
                {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <span className="font-mono">{device.base}</span>
                <span>
                  {device.kind} · {device.asset_id}
                </span>
                <span className="text-muted-foreground text-xs">
                  {device.registers.filter((register) => register.powerflow_server !== "no").length} of {device.registers.length} points served
                </span>
              </Button>
              {isOpen && (
                <div className="px-3 pb-3">
                  <DeviceRegisters device={device} servedOnly={servedOnly} />
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

function SiteMaps({ siteName }: { siteName: string }) {
  const maps = useQuery({ queryKey: powerflowKeys.modbusMaps(siteName), queryFn: () => powerflowApi.listModbusMaps(siteName), retry: false });
  const [open, setOpen] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: powerflowKeys.modbusMap(siteName, open ?? ""),
    queryFn: () => powerflowApi.getModbusMap(siteName, open as string),
    enabled: Boolean(open),
    retry: false,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Per-asset Modbus maps · {siteName}</CardTitle>
        <CardDescription>Stored with the site (one unit id per asset). The Modbus server above doesn't use them. View only.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {maps.isLoading && <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />}
        {maps.isError && <p role="alert" className="text-destructive">{getErrorMessage(maps.error)}</p>}
        {(maps.data ?? []).map((summary) => {
          const isOpen = open === summary.asset;
          return (
            <div key={summary.asset} className="border border-border rounded-md">
              <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => setOpen(isOpen ? null : summary.asset)}>
                {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <span>{summary.asset}</span>
                <span className="text-muted-foreground text-xs">
                  unit {summary.unit_id} · port {summary.port} · {summary.points} points
                </span>
                {summary.orphaned && <Badge variant="outline">orphaned</Badge>}
              </Button>
              {isOpen && (
                <div className="px-3 pb-3">
                  {detail.isLoading && <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />}
                  {detail.data && (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Point</TableHead>
                          <TableHead>Register</TableHead>
                          <TableHead>Address</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Scale</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.data.points.map((point) => (
                          <TableRow key={`${point.register_type}-${point.address}`}>
                            <TableCell>{point.point}</TableCell>
                            <TableCell>{point.register_type}</TableCell>
                            <TableCell className="font-mono">{point.address}</TableCell>
                            <TableCell>{point.data_type}</TableCell>
                            <TableCell>{point.scale ?? 1}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function ModbusPanel({ siteName }: { siteName: string }) {
  return (
    <div className="space-y-4">
      <AggregatorLayout />
      <SiteMaps siteName={siteName} />
    </div>
  );
}
