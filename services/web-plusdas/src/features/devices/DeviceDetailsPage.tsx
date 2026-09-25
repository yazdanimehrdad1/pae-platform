import { useState } from "react";
import { useLocation, useNavigate, useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription,
  AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { ArrowLeft, Activity, Info, Radio, Pencil, Plus, Trash2, RotateCcw, Save, Database } from "lucide-react";
import type { Device, DeviceCreateRequest, DeviceScanRanges } from "@/shared/types/device";
import type { DevicePoint, DevicePointCreateRequest, DevicePointUpdateRequest } from "@/shared/types/device-point";
import { devicesApi, type PingResult } from "@/api/devices";
import { getErrorMessage } from "@/api/client";
import { toast } from "@/shared/hooks/use-toast";
import { DeviceFormDialog } from "@/features/sites/DeviceFormDialog";
import { DevicePointsGrid } from "@/features/devices/DevicePointsGrid";

type ScanRangeKind = 'holding' | 'input' | 'coils';
const SCAN_RANGE_KINDS: ScanRangeKind[] = ['holding', 'input', 'coils'];
type EditableRange = { start_index: string; count: string };
type EditableScanRanges = Record<ScanRangeKind, EditableRange[]>;

export default function DeviceDetails() {
  const { deviceId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const device: Device | undefined = location.state?.device;
  const selectedSite = location.state?.selectedSite;
  const deviceIdNum = device ? Number(device.id) : NaN;
  const queryClient = useQueryClient();

  const { data: liveDevice } = useQuery({
    queryKey: ['device-record', selectedSite?.id, deviceIdNum],
    queryFn: () => devicesApi.getRecord(selectedSite.id, deviceIdNum),
    enabled: !!selectedSite?.id && !!device && Number.isFinite(deviceIdNum),
  });

  const deviceRecordKey = ['device-record', selectedSite?.id, deviceIdNum];

  const isModbus = (liveDevice?.protocol ?? device?.protocol)?.toLowerCase() === 'modbus';
  const effectiveName = liveDevice?.name ?? device?.name ?? '';
  const effectiveMake = liveDevice?.vendor ?? device?.make ?? '';
  const effectiveModel = liveDevice?.model ?? device?.model ?? '';
  const effectiveType = liveDevice?.type ?? device?.type ?? '';
  const effectiveProtocol = liveDevice?.protocol ?? device?.protocol ?? '';
  const effectiveHost = liveDevice?.host ?? device?.location ?? '';
  const effectiveDescription = liveDevice?.description ?? device?.description ?? '';
  const effectivePollEnabled = liveDevice ? liveDevice.poll_enabled : device?.modbusConfig?.pollEnabled;
  const effectiveCommStatus = liveDevice ? (liveDevice.poll_enabled ? 'connected' : 'timeout') : (device?.commStatus ?? '');
  const effectiveUpdatedAt = liveDevice?.updated_at ?? device?.lastUpdate ?? '';
  const effectivePointsCount = liveDevice
    ? liveDevice.points.standardized.length + liveDevice.points.native.length + liveDevice.points.virtual.length
    : (device?.points.length ?? 0);

  const [editDeviceOpen, setEditDeviceOpen] = useState(false);
  const updateDeviceMutation = useMutation({
    mutationFn: (payload: DeviceCreateRequest) => devicesApi.update(selectedSite.id, deviceIdNum, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deviceRecordKey });
      queryClient.invalidateQueries({ queryKey: ['site-devices'] });
      toast({ title: "Device updated" });
    },
    onError: (error) => toast({ title: "Failed to update device", description: getErrorMessage(error), variant: "destructive" }),
  });

  const pointsQueryKey = ['device-points', selectedSite?.id, deviceIdNum];
  const { data: allPoints = [] } = useQuery({
    queryKey: pointsQueryKey,
    queryFn: () => devicesApi.getPoints(selectedSite.id, deviceIdNum, { include_deleted: true }),
    enabled: !!selectedSite?.id && Number.isFinite(deviceIdNum),
  });
  const activePoints = allPoints.filter(p => !p.deleted_at);
  const deletedPoints = allPoints.filter(p => p.deleted_at);

  const invalidatePoints = () => {
    queryClient.invalidateQueries({ queryKey: pointsQueryKey });
    queryClient.invalidateQueries({ queryKey: deviceRecordKey });
  };

  const [deletingPoint, setDeletingPoint] = useState<DevicePoint | null>(null);
  const [hardDeleteConfirmed, setHardDeleteConfirmed] = useState(false);

  const savePointsMutation = useMutation({
    mutationFn: async (changes: {
      updates: { id: number; payload: DevicePointUpdateRequest }[];
      creates: DevicePointCreateRequest[];
    }) => {
      for (const u of changes.updates) {
        await devicesApi.updatePoint(selectedSite.id, deviceIdNum, u.id, u.payload);
      }
      if (changes.creates.length > 0) {
        await devicesApi.bulkUpsertPoints(selectedSite.id, deviceIdNum, changes.creates);
      }
    },
    onSuccess: () => {
      invalidatePoints();
      toast({ title: "Points saved" });
    },
    onError: (error) => toast({ title: "Failed to save points", description: getErrorMessage(error), variant: "destructive" }),
  });

  const deletePointsMutation = useMutation({
    mutationFn: ({ id, mode }: { id: number; mode: 'soft' | 'hard' }) =>
      devicesApi.deletePoints(selectedSite.id, deviceIdNum, [id], { mode, confirm: mode === 'hard' }),
    onSuccess: (_, vars) => {
      invalidatePoints();
      toast({ title: vars.mode === 'hard' ? "Point permanently deleted" : "Point deleted" });
      setDeletingPoint(null);
      setHardDeleteConfirmed(false);
    },
    onError: (error) => toast({ title: "Failed to delete point", description: getErrorMessage(error), variant: "destructive" }),
  });

  const restorePointMutation = useMutation({
    mutationFn: (id: number) => devicesApi.restorePoint(selectedSite.id, deviceIdNum, id),
    onSuccess: () => {
      invalidatePoints();
      toast({ title: "Point restored" });
    },
    onError: (error) => toast({ title: "Failed to restore point", description: getErrorMessage(error), variant: "destructive" }),
  });

  const closeDeletePointDialog = (open: boolean) => {
    if (!open) {
      setDeletingPoint(null);
      setHardDeleteConfirmed(false);
    }
  };

  const setScanRangesMutation = useMutation({
    mutationFn: (ranges: DeviceScanRanges) => devicesApi.setScanRanges(selectedSite.id, deviceIdNum, ranges),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deviceRecordKey });
      toast({ title: "Scan ranges saved and locked" });
      setIsEditingRanges(false);
      setDraft(null);
    },
    onError: (error) => toast({ title: "Failed to save scan ranges", description: getErrorMessage(error), variant: "destructive" }),
  });

  const resetScanRangesMutation = useMutation({
    mutationFn: () => devicesApi.resetScanRanges(selectedSite.id, deviceIdNum),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: deviceRecordKey });
      toast({ title: "Scan ranges reset to auto-computed" });
    },
    onError: (error) => toast({ title: "Failed to reset scan ranges", description: getErrorMessage(error), variant: "destructive" }),
  });

  const [isEditingRanges, setIsEditingRanges] = useState(false);
  const [draft, setDraft] = useState<EditableScanRanges | null>(null);

  const startEditingRanges = () => {
    const source = liveDevice?.scan_ranges ?? { holding: [], input: [], coils: [] };
    setDraft({
      holding: source.holding.map(r => ({ start_index: String(r.start_index), count: String(r.count) })),
      input: source.input.map(r => ({ start_index: String(r.start_index), count: String(r.count) })),
      coils: source.coils.map(r => ({ start_index: String(r.start_index), count: String(r.count) })),
    });
    setIsEditingRanges(true);
  };

  const cancelEditingRanges = () => {
    setDraft(null);
    setIsEditingRanges(false);
  };

  const addRow = (kind: ScanRangeKind) => {
    setDraft(prev => prev && { ...prev, [kind]: [...prev[kind], { start_index: '', count: '' }] });
  };

  const removeRow = (kind: ScanRangeKind, index: number) => {
    setDraft(prev => prev && { ...prev, [kind]: prev[kind].filter((_, i) => i !== index) });
  };

  const updateRow = (kind: ScanRangeKind, index: number, field: keyof EditableRange, value: string) => {
    setDraft(prev => prev && {
      ...prev,
      [kind]: prev[kind].map((row, i) => i === index ? { ...row, [field]: value } : row),
    });
  };

  const isDraftValid = !!draft && SCAN_RANGE_KINDS.every(kind => draft[kind].every(row => {
    const start = Number(row.start_index);
    const count = Number(row.count);
    return row.start_index !== '' && row.count !== '' &&
      Number.isInteger(start) && start >= 0 && start <= 65535 &&
      Number.isInteger(count) && count >= 1;
  }));

  const saveScanRanges = () => {
    if (!draft || !isDraftValid) return;
    const ranges: DeviceScanRanges = {
      holding: draft.holding.map(r => ({ start_index: Number(r.start_index), count: Number(r.count) })),
      input: draft.input.map(r => ({ start_index: Number(r.start_index), count: Number(r.count) })),
      coils: draft.coils.map(r => ({ start_index: Number(r.start_index), count: Number(r.count) })),
    };
    setScanRangesMutation.mutate(ranges);
  };

  const [pingResult, setPingResult] = useState<PingResult | null>(null);
  const [pinging, setPinging] = useState(false);
  const [pingError, setPingError] = useState<string | null>(null);

  const handlePing = async () => {
    if (!device || !selectedSite) return;
    setPinging(true);
    setPingResult(null);
    setPingError(null);
    try {
      const result = await devicesApi.ping(selectedSite.id, device.id);
      setPingResult(result);
    } catch {
      setPingError('Ping request failed');
    } finally {
      setPinging(false);
    }
  };

  const deviceMetadata = device ? {
    Status: {
      'Last Update': effectiveUpdatedAt,
      'Firmware': device.firmware || '—',
      'Points': String(effectivePointsCount),
      'Description': effectiveDescription || '—',
    },
    Identification: {
      'Device ID': device.id,
      'Name': effectiveName,
      'Make': effectiveMake,
      'Model': effectiveModel,
      'Serial Number': device.serialNumber,
      'Type': effectiveType,
    },
    Connectivity: {
      'Protocol': effectiveProtocol || '—',
      'Host / IP': effectiveHost,
      'Communication': effectiveCommStatus,
      ...(isModbus ? {
        'Port': String(liveDevice?.port ?? device.modbusConfig?.port ?? ''),
        'Server Address': String(liveDevice?.server_address ?? device.modbusConfig?.serverAddress ?? ''),
        'Address Mode': liveDevice?.modbus_address_mode ?? device.modbusConfig?.addressMode ?? '',
        'Poll Enabled': effectivePollEnabled ? 'Yes' : 'No',
        'Read from Aggregator': (liveDevice ? liveDevice.read_from_aggregator : device.modbusConfig?.readFromAggregator) ? 'Yes' : 'No',
        'Scan Ranges Locked': (liveDevice ? liveDevice.scan_ranges_locked : device.modbusConfig?.scanRangesLocked) ? 'Yes' : 'No',
      } : {}),
    },
  } : null;

  const scanRangeRows = liveDevice?.scan_ranges
    ? SCAN_RANGE_KINDS.flatMap(kind =>
        liveDevice.scan_ranges![kind].map((r, i) => ({
          type: kind.charAt(0).toUpperCase() + kind.slice(1),
          index: i,
          startIndex: r.start_index,
          count: r.count,
          end: r.start_index + r.count - 1,
        }))
      )
    : [];

  if (!device) {
    return (
      <div className="p-6 text-center">
        <h2 className="text-xl font-bold">Device Not Found</h2>
        <Button className="mt-4" onClick={() => navigate('/site-devices')}>
          Back to Devices
        </Button>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <Breadcrumb className="mb-4">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/sites">Sites</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/site-devices" state={{ selectedSite: location.state?.selectedSite }}>
                  Devices
                </Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{effectiveName}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground flex items-center gap-3">
              {effectiveName}
              <Badge variant={device.status === 'online' ? 'default' : 'secondary'} className={
                device.status === 'online' ? 'bg-success text-success-foreground' :
                  device.status === 'warning' ? 'bg-warning text-warning-foreground' : 'bg-destructive text-destructive-foreground'
              }>
                {device.status}
              </Badge>
            </h1>
            <p className="text-muted-foreground mt-1">
              {effectiveMake} {effectiveModel}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={!liveDevice} onClick={() => setEditDeviceOpen(true)}>
              <Pencil className="w-4 h-4 mr-2" />Edit Device
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Info className="w-5 h-5" />
                Device Metadata
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {Object.entries(deviceMetadata!).map(([section, data]) => (
                <div key={section} className="bg-muted/50 rounded-lg p-4 border-2 border-success">
                  <h4 className="font-medium mb-3 capitalize text-sm text-foreground/80 border-b border-border/50 pb-1">{section}</h4>
                  <div className="grid grid-cols-2 gap-4">
                    {Object.entries(data).map(([key, value]) => (
                      <div key={key}>
                        <span className="text-xs text-muted-foreground block">{key}</span>
                        <span className="text-sm font-medium">{value}</span>
                      </div>
                    ))}
                  </div>
                  {section === 'Connectivity' && isModbus && (
                    <div className="mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-muted-foreground">Scan Ranges</span>
                        <div className="flex items-center gap-2">
                          {!isEditingRanges ? (
                            <>
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <span>
                                      <Button
                                        variant="outline" size="sm" className="h-7 gap-1 text-xs"
                                        disabled={!liveDevice?.scan_ranges_locked || resetScanRangesMutation.isPending}
                                        onClick={() => resetScanRangesMutation.mutate()}
                                      >
                                        <RotateCcw className="w-3 h-3" />Reset to Auto
                                      </Button>
                                    </span>
                                  </TooltipTrigger>
                                  {!liveDevice?.scan_ranges_locked && <TooltipContent><p>Already auto-computed</p></TooltipContent>}
                                </Tooltip>
                              </TooltipProvider>
                              <Button variant="outline" size="sm" className="h-7 gap-1 text-xs" disabled={!liveDevice} onClick={startEditingRanges}>
                                <Pencil className="w-3 h-3" />Edit Scan Ranges
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={cancelEditingRanges}>Cancel</Button>
                              <Button
                                size="sm" className="h-7 gap-1 text-xs"
                                disabled={!isDraftValid || setScanRangesMutation.isPending}
                                onClick={saveScanRanges}
                              >
                                <Save className="w-3 h-3" />Save & Lock
                              </Button>
                            </>
                          )}
                        </div>
                      </div>

                      {!isEditingRanges ? (
                        scanRangeRows.length > 0 ? (
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-xs text-muted-foreground border-b">
                                <th className="text-left font-medium pb-1">Register</th>
                                <th className="text-right font-medium pb-1">Start</th>
                                <th className="text-right font-medium pb-1">End</th>
                                <th className="text-right font-medium pb-1">Count</th>
                              </tr>
                            </thead>
                            <tbody>
                              {scanRangeRows.map((row) => (
                                <tr key={`${row.type}-${row.index}`} className="border-b border-border/50 last:border-0">
                                  <td className="py-1 font-medium">{row.type}</td>
                                  <td className="py-1 text-right tabular-nums">{row.startIndex}</td>
                                  <td className="py-1 text-right tabular-nums">{row.end}</td>
                                  <td className="py-1 text-right tabular-nums">{row.count}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p className="text-xs text-muted-foreground">
                            {liveDevice ? 'No scan ranges (device has no NATIVE points).' : 'Loading...'}
                          </p>
                        )
                      ) : (
                        <div className="space-y-3">
                          {SCAN_RANGE_KINDS.map(kind => (
                            <div key={kind}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-xs font-medium capitalize">{kind}</span>
                                <Button variant="ghost" size="sm" className="h-6 gap-1 text-xs" onClick={() => addRow(kind)}>
                                  <Plus className="w-3 h-3" />Add Range
                                </Button>
                              </div>
                              {draft?.[kind].length === 0 ? (
                                <p className="text-xs text-muted-foreground mb-2">No ranges</p>
                              ) : (
                                <div className="space-y-1 mb-2">
                                  {draft?.[kind].map((row, i) => (
                                    <div key={i} className="flex items-center gap-2">
                                      <Input
                                        type="number" className="h-7 w-24" placeholder="Start"
                                        value={row.start_index}
                                        onChange={(e) => updateRow(kind, i, 'start_index', e.target.value)}
                                      />
                                      <Input
                                        type="number" className="h-7 w-24" placeholder="Count"
                                        value={row.count}
                                        onChange={(e) => updateRow(kind, i, 'count', e.target.value)}
                                      />
                                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeRow(kind, i)}>
                                        <Trash2 className="w-3 h-3" />
                                      </Button>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Live Status
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="min-h-[200px] flex flex-col items-center justify-center text-muted-foreground bg-muted/10 rounded-md border-dashed border-2">
                <Activity className="w-12 h-12 mb-4 opacity-50" />
                <p>Device Control Component Placeholder</p>
              </div>

              <div className="border-t pt-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium">Device Ping</span>
                  <Button size="sm" onClick={handlePing} disabled={pinging}>
                    <Radio className="w-4 h-4 mr-2" />
                    {pinging ? 'Pinging...' : 'Ping'}
                  </Button>
                </div>

                {pingError && (
                  <div className="text-sm text-destructive bg-destructive/10 rounded-md p-3">
                    {pingError}
                  </div>
                )}

                {pingResult && (
                  <div className="bg-muted/50 rounded-lg p-4 border-2 border-success space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Reachable</span>
                      <Badge className={pingResult.reachable ? 'bg-success text-success-foreground' : 'bg-destructive text-destructive-foreground'}>
                        {pingResult.reachable ? 'Yes' : 'No'}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Latency</span>
                      <span className="font-medium tabular-nums">{pingResult.latency_ms != null ? `${pingResult.latency_ms.toFixed(2)} ms` : '—'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Host</span>
                      <span className="font-medium">{pingResult.host}:{pingResult.port}</span>
                    </div>
                    {pingResult.error && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Error</span>
                        <span className="font-medium text-destructive">{pingResult.error}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="w-5 h-5" />
              Device Points
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="active">
              <TabsList>
                <TabsTrigger value="active">Active ({activePoints.length})</TabsTrigger>
                <TabsTrigger value="deleted">Deleted ({deletedPoints.length})</TabsTrigger>
              </TabsList>

              <TabsContent value="active">
                <DevicePointsGrid
                  points={activePoints}
                  disabled={!liveDevice}
                  isSaving={savePointsMutation.isPending}
                  onSave={(changes) => savePointsMutation.mutateAsync(changes)}
                  onRequestDelete={(p) => setDeletingPoint(p)}
                />
              </TabsContent>

              <TabsContent value="deleted">
                {deletedPoints.length === 0 ? (
                  <p className="text-muted-foreground py-12 text-center">No deleted points</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Deleted</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {deletedPoints.map((p) => (
                        <TableRow key={p.id}>
                          <TableCell className="font-medium">{p.name}</TableCell>
                          <TableCell><Badge variant="outline">{p.category}</Badge></TableCell>
                          <TableCell>{p.deleted_at ? new Date(p.deleted_at).toLocaleString() : '—'}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="outline" size="sm" className="gap-1"
                                disabled={restorePointMutation.isPending}
                                onClick={() => restorePointMutation.mutate(p.id)}
                              >
                                <RotateCcw className="w-3 h-3" />Restore
                              </Button>
                              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeletingPoint(p)}>
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      <DeviceFormDialog
        open={editDeviceOpen}
        onOpenChange={setEditDeviceOpen}
        device={liveDevice}
        onSubmit={(payload) => updateDeviceMutation.mutateAsync(payload)}
      />

      <AlertDialog open={deletingPoint !== null} onOpenChange={closeDeletePointDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{deletingPoint?.name}"?</AlertDialogTitle>
            <AlertDialogDescription>
              {deletingPoint?.deleted_at
                ? "This point is already soft-deleted. Permanent deletion cannot be undone."
                : "Soft delete preserves the point — it can be restored later from the Deleted tab. Permanent deletion cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="flex items-center gap-2 py-2">
            <Checkbox
              id="point-hard-delete-confirm"
              checked={hardDeleteConfirmed}
              onCheckedChange={(checked) => setHardDeleteConfirmed(checked === true)}
            />
            <label htmlFor="point-hard-delete-confirm" className="text-sm text-muted-foreground">
              I understand this cannot be undone
            </label>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            {!deletingPoint?.deleted_at && (
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault();
                  if (deletingPoint) deletePointsMutation.mutate({ id: deletingPoint.id, mode: "soft" });
                }}
                disabled={deletePointsMutation.isPending}
              >
                Delete
              </AlertDialogAction>
            )}
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={!hardDeleteConfirmed || deletePointsMutation.isPending}
              onClick={(e) => {
                e.preventDefault();
                if (deletingPoint) deletePointsMutation.mutate({ id: deletingPoint.id, mode: "hard" });
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
