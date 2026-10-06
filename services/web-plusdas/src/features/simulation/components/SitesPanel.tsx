import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { RunState, SiteList } from "@/api/types/powerflow";
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
import { useActivateSite, useRefreshPowerflow } from "../hooks/usePowerflow";

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
      toast({ title: `Deleted ${name}` });
      if (name === selected) onSelect(sites.active);
    },
    onError: (error) => toast({ title: "Deleting the site failed", description: getErrorMessage(error), variant: "destructive" }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Stored sites</CardTitle>
        <CardDescription>
          Site configurations stored in powerflow's database, the only place they live. One is active (loaded
          into the simulator). Default sites ship with powerflow: they can be edited but not deleted.
        </CardDescription>
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
            {sites.sites.map(({ name, category }) => {
              const isDefault = category === "default";
              const isActive = name === sites.active;
              // The database's startup choice; differs from the running site only under an ACTIVE_SITE override.
              const isStoredActive = name === sites.stored_active && !isActive;
              return (
                <TableRow key={name} data-site-row={name}>
                  <TableCell>
                    <Button variant="link" className="px-0" onClick={() => onSelect(name)}>
                      {name}
                    </Button>
                  </TableCell>
                  <TableCell className="space-x-2">
                    {isDefault && <Badge variant="secondary">default</Badge>}
                    {isActive && <Badge className="bg-success/20 text-success border-success" variant="outline">active</Badge>}
                    {isStoredActive && <Badge variant="outline">loaded at startup</Badge>}
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
                      disabled={isDefault || isActive || isStoredActive || remove.isPending}
                      title={isDefault ? "Default sites can't be deleted" : undefined}
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
                The stored site is removed from powerflow's database for good: there is no copy to restore it
                from.
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

// The stored sites (powerflow's database is the only store): activate or delete one.
export function SitesPanel(props: Props) {
  return <StoredSites {...props} />;
}
