import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription,
  AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { toast } from "@/shared/hooks/use-toast";
import { sitesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { SiteCreateRequest, SiteRecord } from "@/shared/types/site";
import { Plus, Pencil, Trash2, RotateCcw, AlertTriangle } from "lucide-react";
import { SiteFormDialog } from "./SiteFormDialog";

export default function ManageSitesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: sites = [], isLoading, isError } = useQuery({
    queryKey: ["sites", "manage"],
    queryFn: sitesApi.list,
  });

  const activeSites = sites.filter((s) => !s.deleted_at);
  const deletedSites = sites.filter((s) => s.deleted_at);

  const [formOpen, setFormOpen] = useState(false);
  const [editingSite, setEditingSite] = useState<SiteRecord | undefined>(undefined);
  const [deletingSite, setDeletingSite] = useState<SiteRecord | null>(null);
  const [hardDeleteConfirmed, setHardDeleteConfirmed] = useState(false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["sites"] });

  const createMutation = useMutation({
    mutationFn: (payload: SiteCreateRequest) => sitesApi.create(payload),
    onSuccess: () => {
      invalidate();
      toast({ title: "Site created" });
    },
    onError: (error) => toast({ title: "Failed to create site", description: getErrorMessage(error), variant: "destructive" }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: SiteCreateRequest }) => sitesApi.update(id, payload),
    onSuccess: () => {
      invalidate();
      toast({ title: "Site updated" });
    },
    onError: (error) => toast({ title: "Failed to update site", description: getErrorMessage(error), variant: "destructive" }),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ id, mode }: { id: number; mode: "soft" | "hard" }) =>
      sitesApi.remove(id, { mode, confirm: mode === "hard" }),
    onSuccess: (_, vars) => {
      invalidate();
      toast({ title: vars.mode === "hard" ? "Site permanently deleted" : "Site deleted" });
      setDeletingSite(null);
      setHardDeleteConfirmed(false);
    },
    onError: (error) => toast({ title: "Failed to delete site", description: getErrorMessage(error), variant: "destructive" }),
  });

  const restoreMutation = useMutation({
    mutationFn: (id: number) => sitesApi.restore(id),
    onSuccess: () => {
      invalidate();
      toast({ title: "Site restored" });
    },
    onError: (error) => toast({ title: "Failed to restore site", description: getErrorMessage(error), variant: "destructive" }),
  });

  const openCreate = () => {
    setEditingSite(undefined);
    setFormOpen(true);
  };

  const openEdit = (site: SiteRecord) => {
    setEditingSite(site);
    setFormOpen(true);
  };

  const handleFormSubmit = async (payload: SiteCreateRequest) => {
    if (editingSite) {
      await updateMutation.mutateAsync({ id: editingSite.site_id, payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
  };

  const closeDeleteDialog = (open: boolean) => {
    if (!open) {
      setDeletingSite(null);
      setHardDeleteConfirmed(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Failed to load sites</h3>
          <p className="text-muted-foreground">Check your connection and try again</p>
        </div>
      </div>
    );
  }

  const renderRow = (site: SiteRecord, variant: "active" | "deleted") => (
    <TableRow key={site.site_id}>
      <TableCell className="font-medium">{site.name}</TableCell>
      <TableCell>{site.client_id}</TableCell>
      <TableCell>{site.location.city}, {site.location.state}</TableCell>
      <TableCell>{site.operator}</TableCell>
      <TableCell>{site.capacity}</TableCell>
      <TableCell>{site.device_count}</TableCell>
      <TableCell>
        {variant === "active"
          ? new Date(site.updated_at).toLocaleString()
          : new Date(site.deleted_at as string).toLocaleString()}
      </TableCell>
      <TableCell className="text-right">
        {variant === "active" ? (
          <div className="flex justify-end gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(site)}>
              <Pencil className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeletingSite(site)}>
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        ) : (
          <div className="flex justify-end gap-1">
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              disabled={restoreMutation.isPending}
              onClick={() => restoreMutation.mutate(site.site_id)}
            >
              <RotateCcw className="w-3 h-3" />Restore
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeletingSite(site)}>
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        )}
      </TableCell>
    </TableRow>
  );

  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <Breadcrumb className="mb-4">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <button onClick={() => navigate("/sites")} className="cursor-pointer">Sites</button>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>Manage</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Manage Sites</h1>
            <p className="text-muted-foreground mt-1">Create, edit, delete, and restore sites</p>
          </div>
          <Button onClick={openCreate} className="gap-2">
            <Plus className="w-4 h-4" />Add Site
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <Tabs defaultValue="active">
          <TabsList>
            <TabsTrigger value="active">Active ({activeSites.length})</TabsTrigger>
            <TabsTrigger value="deleted">Deleted ({deletedSites.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="active">
            {activeSites.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center">No active sites</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Client ID</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Operator</TableHead>
                    <TableHead>Capacity</TableHead>
                    <TableHead>Devices</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>{activeSites.map((site) => renderRow(site, "active"))}</TableBody>
              </Table>
            )}
          </TabsContent>

          <TabsContent value="deleted">
            {deletedSites.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center">No deleted sites</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Client ID</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead>Operator</TableHead>
                    <TableHead>Capacity</TableHead>
                    <TableHead>Devices</TableHead>
                    <TableHead>Deleted</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>{deletedSites.map((site) => renderRow(site, "deleted"))}</TableBody>
              </Table>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <SiteFormDialog open={formOpen} onOpenChange={setFormOpen} site={editingSite} onSubmit={handleFormSubmit} />

      <AlertDialog open={deletingSite !== null} onOpenChange={closeDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{deletingSite?.name}"?</AlertDialogTitle>
            <AlertDialogDescription>
              {deletingSite?.deleted_at
                ? "This site is already soft-deleted. Permanent deletion cannot be undone and requires the site to have no active devices."
                : "Soft delete preserves the site and its devices — it can be restored later from the Deleted tab. Permanent deletion cannot be undone and requires the site to have no active devices."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex items-center gap-2 py-2">
            <Checkbox
              id="hard-delete-confirm"
              checked={hardDeleteConfirmed}
              onCheckedChange={(checked) => setHardDeleteConfirmed(checked === true)}
            />
            <label htmlFor="hard-delete-confirm" className="text-sm text-muted-foreground">
              I understand this cannot be undone
            </label>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            {!deletingSite?.deleted_at && (
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault();
                  if (deletingSite) deleteMutation.mutate({ id: deletingSite.site_id, mode: "soft" });
                }}
                disabled={deleteMutation.isPending}
              >
                Delete
              </AlertDialogAction>
            )}
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={!hardDeleteConfirmed || deleteMutation.isPending}
              onClick={(e) => {
                e.preventDefault();
                if (deletingSite) deleteMutation.mutate({ id: deletingSite.site_id, mode: "hard" });
              }}
            >
              Permanently Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
