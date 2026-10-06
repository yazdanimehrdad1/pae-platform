import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Send } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type {
  BessConfig,
  BessMode,
  PvConfig,
  PvSetpointRequest,
  SetpointResult,
} from "@/api/types/powerflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { powerflowKeys } from "../hooks/usePowerflow";

const BESS_MODES: BessMode[] = ["idle", "pq", "offline"];

function ResultLine({ result }: { result: SetpointResult }) {
  const accepted = Object.entries(result.accepted)
    .map(([key, value]) => `${key}=${typeof value === "number" ? Math.round(value * 100) / 100 : value}`)
    .join(", ");
  return (
    <p className="text-xs text-muted-foreground" data-setpoint-result>
      Accepted: {accepted}
      {result.clamped && (
        <Badge variant="outline" className="ml-2 bg-warning/20 text-warning border-warning">
          clamped: {result.flags.join(", ")}
        </Badge>
      )}
    </p>
  );
}

function BessSetpointForm({ bess }: { bess: BessConfig }) {
  const current = useQuery({
    queryKey: [...powerflowKeys.assets, "bess", bess.id],
    queryFn: () => powerflowApi.getBess(bess.id),
    retry: false,
  });
  const [pKw, setPKw] = useState<string>("");
  const [qKvar, setQKvar] = useState<string>("");
  const [mode, setMode] = useState<BessMode | "">("");
  const send = useMutation({
    mutationFn: () =>
      powerflowApi.setBess(bess.id, {
        ...(pKw !== "" ? { p_kw: Number(pKw) } : {}),
        ...(qKvar !== "" ? { q_kvar: Number(qKvar) } : {}),
        ...(mode !== "" ? { mode } : {}),
      }),
    onSuccess: () => current.refetch(),
  });
  const setpoint = current.data?.setpoint;

  return (
    <div className="space-y-2" data-bess-form={bess.id}>
      <div className="grid grid-cols-[1fr_1fr_1fr_auto] items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor={`${bess.id}-p`}>P kW (+ discharge)</Label>
          <Input id={`${bess.id}-p`} type="number" placeholder={setpoint ? String(setpoint.p_kw) : ""} value={pKw} onChange={(event) => setPKw(event.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${bess.id}-q`}>Q kvar</Label>
          <Input id={`${bess.id}-q`} type="number" placeholder={setpoint ? String(setpoint.q_kvar) : ""} value={qKvar} onChange={(event) => setQKvar(event.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Mode</Label>
          <Select value={mode} onValueChange={(value) => setMode(value as BessMode)}>
            <SelectTrigger aria-label={`${bess.id} mode`}>
              <SelectValue placeholder={setpoint?.mode ?? "mode"} />
            </SelectTrigger>
            <SelectContent>
              {BESS_MODES.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" className="gap-1" disabled={send.isPending || (pKw === "" && qKvar === "" && mode === "")} onClick={() => send.mutate()}>
          <Send className="w-4 h-4" /> Send
        </Button>
      </div>
      {setpoint && (
        <p className="text-xs text-muted-foreground">
          Current: {setpoint.p_kw} kW, {setpoint.q_kvar} kvar, {setpoint.mode}
        </p>
      )}
      {send.data && <ResultLine result={send.data} />}
      {send.isError && <p role="alert" className="text-xs text-destructive">{getErrorMessage(send.error)}</p>}
    </div>
  );
}

function PvSetpointForm({ pv }: { pv: PvConfig }) {
  const current = useQuery({
    queryKey: [...powerflowKeys.assets, "pv", pv.id],
    queryFn: () => powerflowApi.getPv(pv.id),
    retry: false,
  });
  const [limitPct, setLimitPct] = useState<string>("");
  const [qKvar, setQKvar] = useState<string>("");
  const [pf, setPf] = useState<string>("");
  const send = useMutation({
    mutationFn: () => {
      const request: PvSetpointRequest = {};
      if (limitPct !== "") request.p_limit_pct = Number(limitPct);
      if (qKvar !== "") request.q_kvar = Number(qKvar);
      else if (pf !== "") request.pf = Number(pf);
      return powerflowApi.setPv(pv.id, request);
    },
    onSuccess: () => current.refetch(),
  });
  const setpoint = current.data?.setpoint;

  return (
    <div className="space-y-2" data-pv-form={pv.id}>
      <div className="grid grid-cols-[1fr_1fr_1fr_auto] items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor={`${pv.id}-limit`}>Curtail to % of P max</Label>
          <Input id={`${pv.id}-limit`} type="number" min={0} max={100} placeholder={setpoint ? String(Math.round(setpoint.p_limit_pct)) : ""} value={limitPct} onChange={(event) => setLimitPct(event.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${pv.id}-q`}>Q kvar (Q mode)</Label>
          <Input id={`${pv.id}-q`} type="number" value={qKvar} disabled={pf !== ""} onChange={(event) => setQKvar(event.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${pv.id}-pf`}>PF (PF mode, |pf| ≥ 0.8)</Label>
          <Input id={`${pv.id}-pf`} type="number" step={0.01} value={pf} disabled={qKvar !== ""} onChange={(event) => setPf(event.target.value)} />
        </div>
        <Button size="sm" className="gap-1" disabled={send.isPending || (limitPct === "" && qKvar === "" && pf === "")} onClick={() => send.mutate()}>
          <Send className="w-4 h-4" /> Send
        </Button>
      </div>
      {setpoint && (
        <p className="text-xs text-muted-foreground">
          Current: limit {Math.round(setpoint.p_limit_kw)} kW ({Math.round(setpoint.p_limit_pct)}%), {setpoint.q_mode} mode,
          Q {setpoint.q_kvar} kvar, PF {setpoint.pf}
        </p>
      )}
      {send.data && <ResultLine result={send.data} />}
      {send.isError && <p role="alert" className="text-xs text-destructive">{getErrorMessage(send.error)}</p>}
    </div>
  );
}

// The active site's assets (configured values) and the BESS/PV setpoints.
export function AssetsPanel({ selectedIsActive }: { selectedIsActive: boolean }) {
  const assets = useQuery({ queryKey: powerflowKeys.assets, queryFn: powerflowApi.getAssets, retry: false });

  if (assets.isLoading) return <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />;
  if (assets.isError) return <p role="alert" className="text-destructive">{getErrorMessage(assets.error)}</p>;
  const data = assets.data;
  if (!data) return null;

  return (
    <div className="space-y-4">
      {!selectedIsActive && (
        <p className="text-sm rounded-md border border-warning/40 bg-warning/10 p-3 text-foreground">
          Setpoints go to the <strong>active</strong> site. These are its assets, not the selected site's.
        </p>
      )}
      {data.bess.map((bess) => (
        <Card key={bess.id}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">BESS · {bess.name ?? bess.id}</CardTitle>
            <CardDescription>
              {bess.inverter.s_rated_kva} kVA · +{bess.inverter.p_discharge_max_kw} / −{bess.inverter.p_charge_max_kw} kW ·{" "}
              {bess.battery.capacity_kwh} kWh · SoC {bess.battery.soc_min_pct ?? 5}–{bess.battery.soc_max_pct ?? 95}% · collector{" "}
              {bess.collector ?? "mv1"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <BessSetpointForm bess={bess} />
          </CardContent>
        </Card>
      ))}
      {data.pv.map((pv) => (
        <Card key={pv.id}>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">PV · {pv.name ?? pv.id}</CardTitle>
            <CardDescription>
              {pv.inverter.s_rated_kva} kVA · {pv.inverter.p_max_kw} kW · {pv.dc_kwp} kWp · {pv.availability.scenario} (
              {pv.availability.source ?? "ac_kw"}) · collector {pv.collector ?? "mv1"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PvSetpointForm pv={pv} />
          </CardContent>
        </Card>
      ))}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Loads and feeder meters</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Kind</TableHead>
                <TableHead>Id</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.loads.map((load) => (
                <TableRow key={`load-${load.id}`}>
                  <TableCell>Load</TableCell>
                  <TableCell>{load.name ?? load.id}</TableCell>
                  <TableCell>
                    bus {load.bus ?? "poi"} · profile {load.profile.scenario} ×{load.profile.scale ?? 1}
                    {load.transformer ? ` · ${load.transformer.s_rated_kva} kVA transformer` : ""}
                  </TableCell>
                </TableRow>
              ))}
              {data.meters.map((meter) => (
                <TableRow key={`meter-${meter.id}`}>
                  <TableCell>Meter</TableCell>
                  <TableCell>{meter.name ?? meter.id}</TableCell>
                  <TableCell>HV side of tx:{meter.transformer} (+ toward the collector)</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
