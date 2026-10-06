import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CalendarClock, Pause, Play, RotateCcw, SkipForward, Square } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { EngineStatus } from "@/api/types/powerflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/shared/hooks/use-toast";
import { useRefreshPowerflow } from "../hooks/usePowerflow";

const STATE_STYLE: Record<EngineStatus["state"], string> = {
  running: "bg-success/20 text-success border-success",
  paused: "bg-warning/20 text-warning border-warning",
  scheduled: "bg-primary/10 text-primary border-primary",
  stopped: "",
};

const SPEEDS = [1, 2, 5, 10, 30, 60, 100];
const utcText = (iso: string) => new Date(iso).toISOString().replace("T", " ").slice(0, 19);

export function RunStateBadge({ state }: { state: EngineStatus["state"] }) {
  return (
    <Badge variant="outline" className={STATE_STYLE[state]} data-run-state={state}>
      {state}
    </Badge>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

export function RunControls({ status }: { status: EngineStatus }) {
  const refresh = useRefreshPowerflow();
  const [stepCount, setStepCount] = useState(1);
  const [startAt, setStartAt] = useState(""); // datetime-local, in the browser's time zone
  const command = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onSuccess: () => refresh(),
    onError: (error) =>
      toast({ title: "Simulation command failed", description: getErrorMessage(error), variant: "destructive" }),
  });
  const run = (action: () => Promise<unknown>) => command.mutate(action);
  const busy = command.isPending;
  const { state } = status;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            Simulation <RunStateBadge state={state} />
          </CardTitle>
          <CardDescription>
            Power flow of the active site, one step every {status.step_s} s of sim time
            {status.speed === 1 ? ", in real time" : `, ${status.speed}× faster than real time`}.
          </CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" className="gap-1" disabled={busy || state === "running"} onClick={() => run(() => powerflowApi.start())}>
            <Play className="w-4 h-4" /> {state === "paused" ? "Resume" : "Start"}
          </Button>
          <Button size="sm" variant="outline" className="gap-1" disabled={busy || state !== "running"} onClick={() => run(powerflowApi.pause)}>
            <Pause className="w-4 h-4" /> Pause
          </Button>
          <Button size="sm" variant="outline" className="gap-1" disabled={busy || state === "stopped"} onClick={() => run(powerflowApi.stop)}>
            <Square className="w-4 h-4" /> Stop
          </Button>
          <Button size="sm" variant="outline" className="gap-1" disabled={busy} onClick={() => run(powerflowApi.reset)}>
            <RotateCcw className="w-4 h-4" /> Reset
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          <Stat label="Sim time" value={new Date(status.sim_time).toISOString().replace("T", " ").slice(0, 19)} />
          <Stat label="Step" value={String(status.step_id)} />
          <Stat label="Converged" value={status.last_converged ? "yes" : "no"} />
          <Stat label="Overruns" value={String(status.overrun_count)} />
          <Stat
            label="Last step"
            value={status.last_step_duration_ms == null ? "–" : `${status.last_step_duration_ms.toFixed(1)} ms`}
          />
          <Stat label="History" value={`${status.history_count} / ${status.history_size}`} />
          <Stat label="Sim start (step 0)" value={utcText(status.start_time)} />
          <Stat label="Start step" value={String(status.start_step)} />
          {status.scheduled_start && <Stat label="Starts at" value={utcText(status.scheduled_start)} />}
          {status.scenario && <Stat label="Event scenario" value={status.scenario} />}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Speed</span>
          <Select value={String(status.speed)} onValueChange={(value) => run(() => powerflowApi.setSpeed(Number(value)))}>
            <SelectTrigger className="w-24" aria-label="Speed">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[...new Set([...SPEEDS, status.speed])].sort((a, b) => a - b).map((speed) => (
                <SelectItem key={speed} value={String(speed)}>
                  {speed}×
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="ml-4 text-sm text-muted-foreground">Start at</span>
          <Input
            type="datetime-local"
            step={1}
            className="w-56"
            value={startAt}
            onChange={(event) => setStartAt(event.target.value)}
            aria-label="Start at"
          />
          <Button
            size="sm"
            variant="outline"
            className="gap-1"
            disabled={busy || !startAt || state === "running"}
            onClick={() => run(() => powerflowApi.start(new Date(startAt).toISOString()))}
          >
            <CalendarClock className="w-4 h-4" /> Schedule
          </Button>
        </div>
        {status.test_mode && (
          <div className="flex items-center gap-2" data-step-controls>
            <Input
              type="number"
              min={1}
              className="w-28"
              value={stepCount}
              onChange={(event) => setStepCount(Math.max(1, Number(event.target.value) || 1))}
              aria-label="Steps"
            />
            <Button
              size="sm"
              variant="outline"
              className="gap-1"
              disabled={busy || state === "running" || state === "scheduled"}
              onClick={() => run(() => powerflowApi.step(stepCount))}
            >
              <SkipForward className="w-4 h-4" /> Step
            </Button>
            <span className="text-xs text-muted-foreground">Test mode: step manually while stopped or paused.</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
