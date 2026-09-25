import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
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
import { devicesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { DeviceCreateRequest, DeviceRecord } from "@/shared/types/device";
import { Plus, Pencil, Trash2, RotateCcw, AlertTriangle, ArrowLeft } from "lucide-react";
import { DeviceFormDialog } from "./DeviceFormDialog";

export default function ManageDevicesPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const selectedSite = location.state?.selectedSite;

  useEffect(() => {
    if (!selectedSite) {
      navigate('/sites');
    }
  }, [selectedSite, navigate]);

  const { data: devices = [], isLoading, isError } = useQuery({
    queryKey: ["site-devices", "manage", selectedSite?.id],
    queryFn: () => devicesApi.list(selectedSite.id),
    enabled: !!selectedSite,
  });

  const activeDevices = devices.filter((d) => !d.deleted_at);
  const deletedDevices = devices.filter((d) => d.deleted_at);

  const [formOpen, setFormOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState<DeviceRecord | undefined>(undefined);
  const [deletingDevice, setDeletingDevice] = useState<DeviceRecord | null>(null);
  const [hardDeleteConfirmed, setHardDeleteConfirmed] = useState(false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["site-devices"] });

  const createMutation = useMutation({
    mutationFn: (payload: DeviceCreateRequest) => devicesApi.create(selectedSite.id, payload),
    onSuccess: () => {
      invalidate();
      toast({ title: "Device created" });
    },
    onError: (error) => toast({ title: "Failed to create device", description: getErrorMessage(error), variant: "destructive" }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: DeviceCreateRequest }) =>
      devicesApi.update(selectedSite.id, id, payload),
    onSuccess: () => {
      invalidate();
      toast({ title: "Device updated" });
    },
    onError: (error) => toast({ title: "Failed to update device", description: getErrorMessage(error), variant: "destructive" }),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ id, mode }: { id: number; mode: "soft" | "hard" }) =>
      devicesApi.remove(selectedSite.id, id, { mode, confirm: mode === "hard" }),
    onSuccess: (_, vars) => {
      invalidate();
      toast({ title: vars.mode === "hard" ? "Device permanently deleted" : "Device deleted" });
      setDeletingDevice(null);
      setHardDeleteConfirmed(false);
    },
    onError: (error) => toast({ title: "Failed to delete device", description: getErrorMessage(error), variant: "destructive" }),
  });

  const restoreMutation = useMutation({
    mutationFn: (id: number) => devicesApi.restore(selectedSite.id, id),
    onSuccess: () => {
      invalidate();
      toast({ title: "Device restored" });
    },
    onError: (error) => toast({ title: "Failed to restore device", description: getErrorMessage(error), variant: "destructive" }),
  });

  const openCreate = () => {
    setEditingDevice(undefined);
    setFormOpen(true);
  };

  const openEdit = (device: DeviceRecord) => {
    setEditingDevice(device);
    setFormOpen(true);
  };

  const handleFormSubmit = async (payload: DeviceCreateRequest) => {
    if (editingDevice) {
      await updateMutation.mutateAsync({ id: editingDevice.device_id, payload });
    } else {
      await createMutation.mutateAsync(payload);
    }
  };

  const closeDeleteDialog = (open: boolean) => {
    if (!open) {
      setDeletingDevice(null);
      setHardDeleteConfirmed(false);
    }
  };

  if (!selectedSite) return null;

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
          <h3 className="text-lg font-semibold mb-2">Failed to load devices</h3>
          <p className="text-muted-foreground">Check your connection and try again</p>
        </div>
      </div>
    );
  }

  const renderRow = (device: DeviceRecord, variant: "active" | "deleted") => (
    <TableRow key={device.device_id}>
      <TableCell className="font-medium">{device.name}</TableCell>
      <TableCell><Badge variant="outline">{device.type}</Badge></TableCell>
      <TableCell>{device.protocol}</TableCell>
      <TableCell>{device.host}:{device.port}</TableCell>
      <TableCell>{device.poll_enabled ? "Yes" : "No"}</TableCell>
      <TableCell>
        {variant === "active"
          ? new Date(device.updated_at).toLocaleString()
          : new Date(device.deleted_at as string).toLocaleString()}
      </TableCell>
      <TableCell className="text-right">
        {variant === "active" ? (
          <div className="flex justify-end gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(device)}>
              <Pencil className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeletingDevice(device)}>
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
              onClick={() => restoreMutation.mutate(device.device_id)}
            >
              <RotateCcw className="w-3 h-3" />Restore
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeletingDevice(device)}>
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
              <BreadcrumbLink asChild>
                <button onClick={() => navigate("/site-devices", { state: { selectedSite } })} className="cursor-pointer">{selectedSite.name}</button>
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
            <h1 className="text-3xl font-bold text-foreground">Manage Devices</h1>
            <p className="text-muted-foreground mt-1">Create, edit, delete, and restore devices for {selectedSite.name}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate('/site-devices', { state: { selectedSite } })}>
              <ArrowLeft className="w-4 h-4 mr-2" />Back to Devices
            </Button>
            <Button onClick={openCreate} className="gap-2">
              <Plus className="w-4 h-4" />Add Device
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <Tabs defaultValue="active">
          <TabsList>
            <TabsTrigger value="active">Active ({activeDevices.length})</TabsTrigger>
            <TabsTrigger value="deleted">Deleted ({deletedDevices.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="active">
            {activeDevices.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center">No active devices</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Protocol</TableHead>
                    <TableHead>Host:Port</TableHead>
                    <TableHead>Polling</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>{activeDevices.map((device) => renderRow(device, "active"))}</TableBody>
              </Table>
            )}
          </TabsContent>

          <TabsContent value="deleted">
            {deletedDevices.length === 0 ? (
              <p className="text-muted-foreground py-12 text-center">No deleted devices</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Protocol</TableHead>
                    <TableHead>Host:Port</TableHead>
                    <TableHead>Polling</TableHead>
                    <TableHead>Deleted</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>{deletedDevices.map((device) => renderRow(device, "deleted"))}</TableBody>
              </Table>
            )}
          </TabsContent>
        </Tabs>
      </div>

      <DeviceFormDialog open={formOpen} onOpenChange={setFormOpen} device={editingDevice} onSubmit={handleFormSubmit} />

      <AlertDialog open={deletingDevice !== null} onOpenChange={closeDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{deletingDevice?.name}"?</AlertDialogTitle>
            <AlertDialogDescription>
              {deletingDevice?.deleted_at
                ? "This device is already soft-deleted. Permanent deletion cannot be undone and will remove all its points and readings."
                : "Soft delete preserves the device and its points — it can be restored later from the Deleted tab. Permanent deletion cannot be undone and will remove all its points and readings."}
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
            {!deletingDevice?.deleted_at && (
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault();
                  if (deletingDevice) deleteMutation.mutate({ id: deletingDevice.device_id, mode: "soft" });
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
                if (deletingDevice) deleteMutation.mutate({ id: deletingDevice.device_id, mode: "hard" });
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
