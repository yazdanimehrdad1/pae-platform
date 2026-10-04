import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, RotateCcw, Trash2 } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { DefaultsRestoreResult, RunState, SiteList } from "@/api/types/powerflow";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "@/shared/hooks/use-toast";
import { powerflowKeys, useActivateSite, useRefreshPowerflow } from "../hooks/usePowerflow";

interface Props {
  sites: SiteList;
  selected: string;
  runState: RunState | undefined;
  onSelect: (name: string) => void;
}

function StoredSites({ sites, selected, runState, onSelect }: Props) {
  const refresh = useRefreshPowerflow();
  const activate = useActivateSite();
  const [deleting, setDeleting] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: (name: string) => powerflowApi.deleteSite(name),
    onSuccess: (_result, name) => {
      refresh();
      toast({ title: `Deleted ${name}`, description: "Restore defaults brings a shipped site back." });
      if (name === selected) onSelect(sites.active);
    },
    onError: (error) => toast({ title: "Deleting the site failed", description: getErrorMessage(error), variant: "destructive" }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Stored sites</CardTitle>
        <CardDescription>Site configurations stored in powerflow. One is active (loaded into the simulator).</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Site</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sites.sites.map((name) => {
              const isActive = name === sites.active;
              return (
                <TableRow key={name} data-site-row={name}>
                  <TableCell>
                    <Button variant="link" className="px-0" onClick={() => onSelect(name)}>
                      {name}
                    </Button>
                  </TableCell>
                  <TableCell className="space-x-2">
                    {isActive && <Badge className="bg-success/20 text-success border-success" variant="outline">active</Badge>}
                    {name === selected && <Badge variant="outline">selected</Badge>}
                  </TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={isActive || activate.isPending}
                      onClick={() => activate.mutate({ name, state: runState })}
                    >
                      {runState && runState !== "stopped" ? "Stop & activate" : "Activate"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1"
                      disabled={isActive || remove.isPending}
                      aria-label={`Delete ${name}`}
                      onClick={() => setDeleting(name)}
                    >
                      <Trash2 className="w-4 h-4" /> Delete
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete {deleting}?</AlertDialogTitle>
              <AlertDialogDescription>
                The stored site and its Modbus maps are removed. A shipped default site can be brought back with Restore
                defaults.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => deleting && remove.mutate(deleting)}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}

function Defaults({ runState }: { runState: RunState | undefined }) {
  const refresh = useRefreshPowerflow();
  const defaults = useQuery({ queryKey: powerflowKeys.defaults, queryFn: powerflowApi.getDefaults, retry: false });
  const [overwrite, setOverwrite] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<DefaultsRestoreResult | null>(null);
  const restore = useMutation({
    mutationFn: () => powerflowApi.restoreDefaults(overwrite),
    onSuccess: (restored) => {
      setResult(restored);
      refresh();
      toast({ title: "Defaults restored", description: `${restored.sites_written.length} site(s) written` });
    },
    onError: (error) => toast({ title: "Restoring defaults failed", description: getErrorMessage(error), variant: "destructive" }),
  });
  const needsStop = overwrite && runState !== undefined && runState !== "stopped";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Shipped defaults</CardTitle>
        <CardDescription>
          The default sites and Modbus maps that ship with powerflow. Restoring copies them into powerflow's database.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {defaults.isLoading && <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />}
        {defaults.data && (
          <ul className="text-sm text-foreground space-y-1">
            {Object.entries(defaults.data.sites).map(([name, maps]) => (
              <li key={name}>
                <span className="font-medium">{name}</span>
                {name === defaults.data.active_site && <span className="text-muted-foreground"> (default active)</span>}
                <span className="text-muted-foreground"> · {maps.length} Modbus maps</span>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-center gap-2">
          <Checkbox id="overwrite" checked={overwrite} onCheckedChange={(checked) => setOverwrite(checked === true)} />
          <Label htmlFor="overwrite">Overwrite stored copies (needs the simulation stopped)</Label>
        </div>
        <Button className="gap-2" variant="outline" disabled={restore.isPending || needsStop} onClick={() => setConfirming(true)}>
          <RotateCcw className="w-4 h-4" /> Restore defaults
        </Button>
        {needsStop && <p className="text-xs text-muted-foreground">Stop the simulation to restore with overwrite.</p>}
        {result && (
          <p className="text-xs text-muted-foreground" data-restore-result>
            Written: {result.sites_written.join(", ") || "none"} · skipped: {result.sites_skipped.join(", ") || "none"}
            {result.active_site_reloaded ? " · the active site was reloaded" : ""}
          </p>
        )}
        <AlertDialog open={confirming} onOpenChange={setConfirming}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Restore the default sites?</AlertDialogTitle>
              <AlertDialogDescription>
                {overwrite
                  ? "The stored default sites and maps are replaced by the shipped files; changes saved to them are lost. Other sites are kept."
                  : "Missing default sites and maps are added back; stored ones are kept."}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => restore.mutate()}>Restore</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
}

export function SitesPanel(props: Props) {
  return (
    <div className="space-y-4">
      <StoredSites {...props} />
      <Defaults runState={props.runState} />
    </div>
  );
}
