import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { siteProfilesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ProfileDevice, SiteFunction, SiteFunctionTestRunResponse } from "@/api/types/siteProfiles";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { formatSiteTime } from "@/shared/lib/siteTime";
import { appliesTo, devicesFor, WINDOWS, withDisplayTimes } from "../lib/functions";

// The site functions the AI may run: backend-ot labels them for the AI assistant, the admin
// approves them here like devices and points, and backend-ot computes them. "Try it" runs one
// exactly as the AI would and shows what the AI gets back (series summarized).

export function SiteFunctionsSection({ siteId, functions, devices, timeZone }: {
  siteId: number;
  functions: SiteFunction[];
  devices: ProfileDevice[];
  timeZone: string;
}) {
  const [trying, setTrying] = useState<SiteFunction | null>(null);
  return (
    <section className="space-y-2">
      <h3 className="font-medium">Site functions <span className="text-muted-foreground font-normal">({functions.length})</span></h3>
      {functions.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          None approved. backend-ot offers the AI only the functions it labels for the AI assistant; approve them under Pending changes.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Function</TableHead>
                <TableHead>What it returns</TableHead>
                <TableHead>Runs for</TableHead>
                <TableHead>Parameters</TableHead>
                <TableHead><span className="sr-only">Actions</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {functions.map(fn => (
                <TableRow key={fn.name}>
                  <TableCell className="font-mono text-xs whitespace-nowrap">{fn.name}</TableCell>
                  <TableCell>{fn.summary}{fn.output === "series" ? <span className="text-muted-foreground"> (series)</span> : null}</TableCell>
                  <TableCell className="whitespace-nowrap">{appliesTo(fn)}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {(fn.parameters ?? []).map(parameter => parameter.name).join(", ") || "—"}
                  </TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" onClick={() => setTrying(fn)} aria-label={`Try ${fn.name}`}>
                      <Play className="w-4 h-4 mr-1" />Try it
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {trying && <TryFunctionDialog siteId={siteId} fn={trying} devices={devicesFor(trying, devices)} timeZone={timeZone} onClose={() => setTrying(null)} />}
    </section>
  );
}

const SELECT_CLASS = "flex h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

function TryFunctionDialog({ siteId, fn, devices, timeZone, onClose }: {
  siteId: number;
  fn: SiteFunction;
  devices: ProfileDevice[];
  timeZone: string;
  onClose: () => void;
}) {
  const [hours, setHours] = useState<number>(24);
  const [showRaw, setShowRaw] = useState(false);
  const [deviceId, setDeviceId] = useState<string>(devices[0] ? String(devices[0].device_id) : "");
  const [values, setValues] = useState<Record<string, string>>({});
  const run = useMutation<SiteFunctionTestRunResponse, unknown>({
    mutationFn: () => {
      const end = new Date();
      const start = new Date(end.getTime() - hours * 3_600_000);
      const parameters: Record<string, number | string> = {};
      for (const parameter of fn.parameters ?? []) {
        const raw = values[parameter.name]?.trim();
        if (!raw) continue;
        parameters[parameter.name] = parameter.type === "integer" || parameter.type === "number" ? Number(raw) : raw;
      }
      return siteProfilesApi.testRunFunction(siteId, fn.name, {
        start: start.toISOString(),
        end: end.toISOString(),
        device_id: fn.kind === "device" ? Number(deviceId) : null,
        parameters,
      });
    },
  });
  const needsDevice = fn.kind === "device";
  const canRun = !run.isPending && (!needsDevice || deviceId !== "");

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-mono text-base">{fn.name}</DialogTitle>
          <DialogDescription>{fn.summary}. Runs in backend-ot; the result below is what the AI gets.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="function-window">Window</Label>
            <select id="function-window" className={SELECT_CLASS} value={hours} onChange={event => setHours(Number(event.target.value))}>
              {WINDOWS.map(window => <option key={window.hours} value={window.hours}>{window.label}</option>)}
            </select>
          </div>
          {needsDevice && (
            <div className="space-y-1">
              <Label htmlFor="function-device">Device</Label>
              {devices.length === 0 ? (
                <p className="text-sm text-muted-foreground">No approved device of type {(fn.device_types ?? []).join(" / ")}.</p>
              ) : (
                <select id="function-device" className={SELECT_CLASS} value={deviceId} onChange={event => setDeviceId(event.target.value)}>
                  {devices.map(device => <option key={device.device_id} value={device.device_id}>{device.name} ({device.type})</option>)}
                </select>
              )}
            </div>
          )}
          {(fn.parameters ?? []).map(parameter => (
            <div key={parameter.name} className="space-y-1">
              <Label htmlFor={`function-parameter-${parameter.name}`}>{parameter.name}{parameter.required ? " *" : ""}</Label>
              <Input
                id={`function-parameter-${parameter.name}`}
                type={parameter.type === "integer" || parameter.type === "number" ? "number" : "text"}
                placeholder={parameter.default != null ? `default ${String(parameter.default)}` : ""}
                value={values[parameter.name] ?? ""}
                onChange={event => setValues(current => ({ ...current, [parameter.name]: event.target.value }))}
              />
              {parameter.description && <p className="text-xs text-muted-foreground">{parameter.description}</p>}
            </div>
          ))}
        </div>
        <div>
          <Button onClick={() => run.mutate()} disabled={!canRun}>
            <Play className="w-4 h-4 mr-1" />{run.isPending ? "Running..." : "Run"}
          </Button>
        </div>
        {run.isError && <p role="alert" className="text-sm text-destructive">{getErrorMessage(run.error)}</p>}
        {run.data && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <p>
                <span className="text-muted-foreground">Window: </span>
                {formatSiteTime(run.data.start, timeZone, { withDate: true })} → {formatSiteTime(run.data.end, timeZone, { withDate: true })}
              </p>
              <label className="inline-flex items-center gap-2 text-muted-foreground">
                <Switch checked={showRaw} onCheckedChange={setShowRaw} aria-label="Show the raw result" />
                Raw (UTC, as the AI gets it)
              </label>
            </div>
            <pre aria-label="Result" className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs">
              {JSON.stringify(showRaw ? run.data.result : withDisplayTimes(run.data.result, timeZone), null, 2)}
            </pre>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
