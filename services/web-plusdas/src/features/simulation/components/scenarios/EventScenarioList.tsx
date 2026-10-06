import { useState } from "react";
import { Pencil, Play, Plus, Square, Trash2 } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ConditionsReport, EventScenario, SiteConfig } from "@/api/types/powerflow";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/shared/hooks/use-toast";
import { useEventScenarios, usePowerflowCommand } from "../../hooks/usePowerflow";
import { EventScenarioEditor } from "./EventScenarioEditor";

interface Props {
  siteName: string;
  config: SiteConfig;
  isActive: boolean;
  report: ConditionsReport | undefined;
}

// The selected site's stored event scenarios: create, edit, delete, and play one (active site).
export function EventScenarioList({ siteName, config, isActive, report }: Props) {
  const scenarios = useEventScenarios(siteName);
  const command = usePowerflowCommand("Event scenario command failed");
  const [editor, setEditor] = useState<{ name: string; scenario: EventScenario } | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<string | null>(null);
  const playing = report?.scenario;
  const isPlaying = (name: string) => playing?.name === name && !playing.finished;

  const edit = async (name: string) => {
    try {
      setEditor({ name, scenario: await powerflowApi.getEventScenario(siteName, name) });
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
            {isActive ? " Start one to play it from the current step." : " Activate the site to play one."}
          </CardDescription>
        </div>
        <Button size="sm" className="gap-1" onClick={() => setEditor(null)}>
          <Plus className="w-4 h-4" /> New scenario
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {playing && (
          <div className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3" data-scenario-status>
            <Badge variant="outline" className={playing.finished ? "" : "bg-primary/10 text-primary border-primary"}>
              {playing.finished ? "finished" : "playing"}
            </Badge>
            <span className="text-sm text-foreground font-medium">{playing.name}</span>
            <span className="text-sm text-muted-foreground">
              {playing.fired} of {playing.total} fired
              {playing.missed > 0 && `, ${playing.missed} missed`}
              {playing.next_step != null && `, next before step ${playing.next_step}`}
            </span>
            <Button size="sm" variant="outline" className="gap-1 ml-auto" disabled={command.isPending} onClick={() => command.mutate(powerflowApi.stopEventScenario)}>
              <Square className="w-4 h-4" /> Stop
            </Button>
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
                <TableHead>Events</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scenarios.data.map((scenario) => (
                <TableRow key={scenario.name} data-scenario-row={scenario.name}>
                  <TableCell>
                    <p className="font-medium text-foreground">{scenario.name}</p>
                    {scenario.description && <p className="text-xs text-muted-foreground">{scenario.description}</p>}
                  </TableCell>
                  <TableCell>{scenario.event_count}</TableCell>
                  <TableCell>
                    {scenario.valid ? (
                      <Badge variant="outline">valid</Badge>
                    ) : (
                      <Badge variant="destructive" title={scenario.problems.join("\n")}>
                        stale: {scenario.problems.length} problem{scenario.problems.length === 1 ? "" : "s"}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      disabled={!isActive || !scenario.valid || command.isPending || isPlaying(scenario.name) || Boolean(playing && !playing.finished)}
                      onClick={() => command.mutate(() => powerflowApi.startEventScenario(scenario.name))}
                    >
                      <Play className="w-4 h-4" /> Start
                    </Button>
                    <Button size="sm" variant="outline" className="gap-1" aria-label={`Edit ${scenario.name}`} onClick={() => edit(scenario.name)}>
                      <Pencil className="w-4 h-4" /> Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      aria-label={`Delete ${scenario.name}`}
                      disabled={isPlaying(scenario.name)}
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
          key={editor?.name ?? "new"}
          siteName={siteName}
          config={config}
          editing={editor}
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
