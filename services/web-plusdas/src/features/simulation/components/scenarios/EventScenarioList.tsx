import { useState } from "react";
import { CalendarClock, Copy, Pencil, Play, Plus, Square, Trash2 } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ConditionsReport, EventScenario, ScenarioStatus, SiteConfig } from "@/api/types/powerflow";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/shared/hooks/use-toast";
import { useEventScenarios, usePowerflowCommand, useSimStatus } from "../../hooks/usePowerflow";
import { describeExpectation, stepWindow } from "../../lib/scenarioEdits";
import { EventScenarioEditor } from "./EventScenarioEditor";

interface Props {
  siteName: string;
  config: SiteConfig;
  isActive: boolean;
  report: ConditionsReport | undefined;
}

const STATE_STYLES: Record<ScenarioStatus["state"], string> = {
  scheduled: "",
  playing: "bg-primary/10 text-primary border-primary",
  finished: "text-muted-foreground",
};

// One run: its state, where it is (its own step, as its events and expected points count), and
// a Stop.
function RunStatus({ run, onStop, disabled }: { run: ScenarioStatus; onStop: () => void; disabled: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3" data-scenario-status={run.name}>
      <Badge variant="outline" className={STATE_STYLES[run.state]}>
        {run.state}
      </Badge>
      <span className="text-sm text-foreground font-medium">{run.name}</span>
      <span className="text-sm text-muted-foreground" data-run-step>
        {run.state === "scheduled"
          ? `starts at sim step ${run.start_step}`
          : `scenario step ${run.current_step} of ${run.length}`}
      </span>
      <span className="text-sm text-muted-foreground">
        {run.fired} of {run.total} events fired
        {run.missed > 0 && `, ${run.missed} missed`}
        {run.next_step != null && `, next before sim step ${run.next_step}`}
      </span>
      <Button size="sm" variant="outline" className="gap-1 ml-auto" aria-label={`Stop ${run.name}`} disabled={disabled} onClick={onStop}>
        <Square className="w-4 h-4" /> {run.state === "finished" ? "Dismiss" : "Stop"}
      </Button>
    </div>
  );
}

// Start a scenario later: at a given engine step (its step 1).
function ScheduleButton({
  name,
  currentStep,
  disabled,
  onSchedule,
}: {
  name: string;
  currentStep: number | undefined;
  disabled: boolean;
  onSchedule: (atStep: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const atStep = Number(value);
  const valid = Number.isInteger(atStep) && currentStep != null && atStep > currentStep;
  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setValue(currentStep != null ? String(currentStep + 10) : "");
      }}
    >
      <PopoverTrigger asChild>
        <Button size="sm" variant="outline" className="gap-1" aria-label={`Schedule ${name}`} disabled={disabled}>
          <CalendarClock className="w-4 h-4" /> Schedule
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 space-y-2">
        <Label htmlFor={`schedule-${name}`}>Start at sim step</Label>
        <Input id={`schedule-${name}`} type="number" min={1} value={value} onChange={(event) => setValue(event.target.value)} />
        <p className="text-xs text-muted-foreground">
          That step is the scenario's step 1. Now: step {currentStep ?? "?"}.
        </p>
        <Button
          size="sm"
          className="w-full"
          disabled={!valid}
          onClick={() => {
            onSchedule(atStep);
            setOpen(false);
          }}
        >
          Schedule
        </Button>
      </PopoverContent>
    </Popover>
  );
}

// The selected site's stored event scenarios: create, edit, delete, and play or schedule them
// (active site). Several can be scheduled or playing at once.
export function EventScenarioList({ siteName, config, isActive, report }: Props) {
  const scenarios = useEventScenarios(siteName);
  const command = usePowerflowCommand("Event scenario command failed");
  const currentStep = useSimStatus().data?.step_id;
  // undefined = closed; null = a new scenario; copy = a new one prefilled from a built-in
  const [editor, setEditor] = useState<{ name: string; scenario: EventScenario; copy?: boolean } | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<string | null>(null);
  const runs = report?.scenarios ?? [];
  // Scheduled or playing (not finished): it can't be started again until it ends or is stopped.
  const isPlaying = (name: string) => runs.some((run) => run.name === name && !run.finished);

  const edit = async (name: string, copy = false) => {
    try {
      setEditor({ name, scenario: await powerflowApi.getEventScenario(siteName, name), copy });
    } catch (error) {
      toast({ title: "Loading the scenario failed", description: getErrorMessage(error), variant: "destructive" });
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>Event scenarios</CardTitle>
          <CardDescription>
            Timelines of injected conditions for {siteName}, stored with the site.
            {isActive
              ? " Start one now or schedule it at a sim step; several can play at once (where they change the same thing, the later change wins)."
              : " Activate the site to play one."}
          </CardDescription>
        </div>
        <Button size="sm" className="gap-1" onClick={() => setEditor(null)}>
          <Plus className="w-4 h-4" /> New scenario
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {runs.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Sim step {currentStep ?? "?"} · {runs.filter((run) => !run.finished).length} scheduled or playing
              </span>
              {runs.length > 1 && (
                <Button size="sm" variant="ghost" disabled={command.isPending} onClick={() => command.mutate(() => powerflowApi.stopEventScenario())}>
                  Stop all
                </Button>
              )}
            </div>
            {runs.map((run) => (
              <RunStatus
                key={run.name}
                run={run}
                disabled={command.isPending}
                onStop={() => command.mutate(() => powerflowApi.stopEventScenario(run.name))}
              />
            ))}
          </div>
        )}
        {scenarios.isError && <p role="alert" className="text-destructive text-sm">{getErrorMessage(scenarios.error)}</p>}
        {scenarios.data && scenarios.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No scenarios yet: create one to trip assets, open breakers or sag the grid on cue.</p>
        )}
        {scenarios.data && scenarios.data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scenario</TableHead>
                <TableHead>What it does</TableHead>
                <TableHead>Impacted points: expected values</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scenarios.data.map((scenario) => (
                <TableRow key={scenario.name} data-scenario-row={scenario.name}>
                  <TableCell className="align-top">
                    <p className="font-medium text-foreground">{scenario.name}</p>
                    {scenario.category === "default" && (
                      <Badge variant="secondary" title="Ships with powerflow: read-only, updated with powerflow">
                        built-in
                      </Badge>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {scenario.event_count} event{scenario.event_count === 1 ? "" : "s"}
                    </p>
                  </TableCell>
                  <TableCell className="align-top text-sm max-w-xs" data-scenario-description>
                    {scenario.description ?? <span className="text-muted-foreground">-</span>}
                  </TableCell>
                  <TableCell className="align-top" data-scenario-points>
                    {scenario.expected_points.length === 0 ? (
                      <span className="text-muted-foreground text-sm">-</span>
                    ) : (
                      <ul className="space-y-0.5 text-xs font-mono">
                        {scenario.expected_points.map((expected, index) => (
                          <li key={index} title={expected.note ?? undefined}>
                            <span className="text-muted-foreground">{expected.device}</span> {describeExpectation(expected)}
                            <span className="text-muted-foreground"> · {stepWindow(expected)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </TableCell>
                  <TableCell className="align-top">
                    {scenario.valid ? (
                      <Badge variant="outline">valid</Badge>
                    ) : (
                      <Badge variant="destructive" title={scenario.problems.join("\n")}>
                        stale: {scenario.problems.length} problem{scenario.problems.length === 1 ? "" : "s"}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="align-top text-right space-x-2 whitespace-nowrap">
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      aria-label={`Start ${scenario.name}`}
                      title={isPlaying(scenario.name) ? "Already scheduled or playing: stop it first" : undefined}
                      disabled={!isActive || !scenario.valid || command.isPending || isPlaying(scenario.name)}
                      onClick={() => command.mutate(() => powerflowApi.startEventScenario(scenario.name))}
                    >
                      <Play className="w-4 h-4" /> Start
                    </Button>
                    <ScheduleButton
                      name={scenario.name}
                      currentStep={currentStep}
                      disabled={!isActive || !scenario.valid || command.isPending || isPlaying(scenario.name)}
                      onSchedule={(atStep) => command.mutate(() => powerflowApi.startEventScenario(scenario.name, atStep))}
                    />
                    {scenario.category === "default" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1"
                        aria-label={`Duplicate ${scenario.name}`}
                        title="Built-in scenarios are read-only: duplicate one to change it"
                        onClick={() => edit(scenario.name, true)}
                      >
                        <Copy className="w-4 h-4" /> Duplicate
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" className="gap-1" aria-label={`Edit ${scenario.name}`} onClick={() => edit(scenario.name)}>
                        <Pencil className="w-4 h-4" /> Edit
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      aria-label={`Delete ${scenario.name}`}
                      title={scenario.category === "default" ? "Built-in scenarios can't be deleted" : undefined}
                      disabled={isPlaying(scenario.name) || scenario.category === "default"}
                      onClick={() => setDeleting(scenario.name)}
                    >
                      <Trash2 className="w-4 h-4" /> Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      {editor !== undefined && (
        <EventScenarioEditor
          key={editor ? `${editor.copy ? "copy:" : ""}${editor.name}` : "new"}
          siteName={siteName}
          config={config}
          editing={editor && !editor.copy ? editor : null}
          copyOf={editor?.copy ? editor : undefined}
          open
          onClose={() => setEditor(undefined)}
        />
      )}
      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting}?</AlertDialogTitle>
            <AlertDialogDescription>The scenario is removed from {siteName} for good.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleting && command.mutate(() => powerflowApi.deleteEventScenario(siteName, deleting))}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
