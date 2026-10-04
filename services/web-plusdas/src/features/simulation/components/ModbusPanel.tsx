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
          <Badge variant="outline" className={data.running ? SUPPORT_STYLE.yes : ""} data-modbus-state>
            {data.running ? "running" : data.enabled ? "not running" : "disabled"}
          </Badge>
        </CardTitle>
        <CardDescription>
          The active site as one aggregator: port {data.port} in the container (1502 on the dev host), unit id {data.unit_id},
          zero-based addresses, holding = input, read-only. Each device owns 100 registers.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.error && (
          <p role="alert" className="text-sm rounded-md border border-destructive/40 bg-destructive/10 p-3 text-destructive">
            Failed to start: {data.error}
          </p>
        )}
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

// The Modbus server of the active site. View only.
export function ModbusPanel() {
  return <AggregatorLayout />;
}
