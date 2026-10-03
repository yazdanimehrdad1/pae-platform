import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Hand, Maximize2, Pencil, Plus, RefreshCw, Save, X, ZoomIn, ZoomOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
import { ToastAction } from "@/components/ui/toast";
import { toast } from "@/shared/hooks/use-toast";
import { devicesApi, sitesApi, sldApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { DeviceRecord } from "@/api/types/devices";
import type { Site } from "@/api/types/sites";
import type { SiteSld, SiteSldResponse, SldNodeValues, SldValuesResponse } from "@/api/types/sld";
import { SiteSldDiagram, type SldEditInteraction } from "./components/SiteSldDiagram";
import { SldEditorPanel, type PickTarget, type RequestPick } from "./editor/SldEditorPanel";
import { useDragToPan } from "./hooks/useDragToPan";
import { useWheelZoom } from "./hooks/useWheelZoom";
import { draftErrors, newDraft, type Cell } from "./lib/sldDraft";
import { SLD_SVG_SELECTOR, computeSldGeometry } from "./lib/sldGeometry";

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.1;
// Leaves room for the container border so a fitted diagram shows no scrollbars.
const FIT_PADDING = 4;
// How often the info boxes refresh, like the alarms page.
const VALUES_REFRESH_MS = 10_000;
const clampZoom = (zoom: number) => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));

interface PendingPick {
  target: PickTarget;
  label: string;
  onPicked: (value: string | Cell) => void;
}

const isConflict = (error: unknown) =>
  (error as { detail?: { error?: string } })?.detail?.error === "ConflictError";

const SLD = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const siteId = searchParams.get("siteId");
  const queryClient = useQueryClient();
  const [zoom, setZoom] = useState(1);
  const sldContainerRef = useRef<HTMLDivElement>(null);
  const [isHandToolActive, setIsHandToolActive] = useState(true);
  const [showValues, setShowValues] = useState(true);

  // Edit mode: a draft of the diagram (null when not editing) and what is selected in it.
  const [editDraft, setEditDraft] = useState<SiteSld | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedCell, setSelectedCell] = useState<Cell | null>(null);
  const [pendingPick, setPendingPick] = useState<PendingPick | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isConfirmingCancel, setIsConfirmingCancel] = useState(false);
  const isEditing = editDraft !== null;

  // Clicks select while editing, so dragging pans only with Space or the middle button then.
  const { cursor, panHandlers } = useDragToPan(sldContainerRef, isHandToolActive && !isEditing);

  const { data: sites = [] } = useQuery<Site[]>({ queryKey: ["sites"], queryFn: sitesApi.getAll });

  // No site in the URL: show the first one, keeping the choice in the URL so a refresh keeps it.
  useEffect(() => {
    if (!siteId && sites.length > 0) setSearchParams({ siteId: sites[0].id }, { replace: true });
  }, [siteId, sites, setSearchParams]);

  const {
    data: storedSld,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<SiteSldResponse | null>({
    queryKey: ["site-sld", siteId],
    queryFn: () => sldApi.getBySite(siteId!),
    enabled: !!siteId,
    retry: false,
  });

  const { data: devices = [] } = useQuery<DeviceRecord[]>({
    queryKey: ["site-device-records", siteId],
    queryFn: () => devicesApi.getRecords(siteId!),
    enabled: !!siteId && isEditing,
  });

  const shownSld = editDraft ?? storedSld?.sld ?? null;
  const geometry = useMemo(
    () => (shownSld ? computeSldGeometry(shownSld, { showInfoBoxes: showValues, editing: isEditing }) : null),
    [shownSld, showValues, isEditing],
  );
  const errors = useMemo(() => (editDraft ? draftErrors(editDraft) : []), [editDraft]);

  const { data: liveValues } = useQuery<SldValuesResponse>({
    queryKey: ["site-sld-values", siteId],
    queryFn: () => sldApi.getValues(siteId!),
    enabled: !!siteId && !!storedSld && showValues,
    refetchInterval: VALUES_REFRESH_MS,
    placeholderData: (previous) => previous,
    retry: false,
  });
  const valuesByNode = useMemo(
    () => new Map<string, SldNodeValues>((liveValues?.nodes ?? []).map((node) => [node.node_id, node])),
    [liveValues],
  );

  const fitToScreen = useCallback(() => {
    const container = sldContainerRef.current;
    if (!container || !geometry) return;
    const { width, height } = container.getBoundingClientRect();
    if (width === 0 || height === 0) return;
    setZoom(clampZoom(Math.min((width - FIT_PADDING) / geometry.viewBox.width, (height - FIT_PADDING) / geometry.viewBox.height)));
  }, [geometry]);

  // Fit when a diagram loads, the layout mode changes or editing starts/stops; not on every edit.
  const latestFit = useRef(fitToScreen);
  latestFit.current = fitToScreen;
  const fitKey = `${siteId}:${storedSld?.revision ?? "none"}:${isEditing}:${showValues}:${!!shownSld}`;
  useLayoutEffect(() => {
    latestFit.current();
  }, [fitKey]);

  useWheelZoom(sldContainerRef, SLD_SVG_SELECTOR, zoom, setZoom, clampZoom);

  const resetEditState = () => {
    setEditDraft(null);
    setIsDirty(false);
    setSelectedId(null);
    setSelectedCell(null);
    setPendingPick(null);
    setSaveError(null);
  };

  const startEditing = () => {
    setEditDraft(storedSld?.sld ?? newDraft());
    setIsDirty(!storedSld);
    setSaveError(null);
  };

  const changeDraft = (draft: SiteSld) => {
    setEditDraft(draft);
    setIsDirty(true);
    setSaveError(null);
  };

  const requestPick: RequestPick = (target, label, onPicked) => setPendingPick({ target, label, onPicked });

  const editing: SldEditInteraction | undefined = isEditing
    ? {
        selectedId,
        selectedCell,
        onSelectElement: (id) => {
          if (pendingPick?.target === "element") {
            pendingPick.onPicked(id);
            setPendingPick(null);
            return;
          }
          setSelectedId(id);
          setSelectedCell(null);
        },
        onSelectCell: (cell) => {
          if (pendingPick?.target === "cell") {
            pendingPick.onPicked(cell);
            setPendingPick(null);
            return;
          }
          setSelectedId(null);
          setSelectedCell(cell);
        },
      }
    : undefined;

  const save = useMutation({
    mutationFn: (draft: SiteSld) => sldApi.save(siteId!, draft, storedSld?.revision ?? null),
    onSuccess: (saved) => {
      queryClient.setQueryData(["site-sld", siteId], saved);
      queryClient.invalidateQueries({ queryKey: ["site-sld-values", siteId] });
      resetEditState();
      toast({ title: "Diagram saved", description: `Revision ${saved.revision}` });
    },
    onError: (saveFailure) => {
      if (isConflict(saveFailure)) {
        toast({
          title: "Changed by someone else",
          description: "The diagram was saved elsewhere since you opened it. Reload it to see the latest version.",
          variant: "destructive",
          action: (
            <ToastAction
              altText="Reload the diagram"
              onClick={() => {
                resetEditState();
                refetch();
              }}
            >
              Reload
            </ToastAction>
          ),
        });
        return;
      }
      setSaveError(getErrorMessage(saveFailure, "Saving the diagram failed"));
    },
  });

  const cancelEditing = () => {
    if (isDirty) setIsConfirmingCancel(true);
    else resetEditState();
  };

  const renderDiagram = () => {
    if (!siteId) {
      return <p className="text-muted-foreground">Select a site to see its single line diagram.</p>;
    }
    if (isLoading) {
      return (
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading single line diagram...</p>
        </div>
      );
    }
    if (isError) {
      return (
        <div className="text-center">
          <AlertTriangle className="w-8 h-8 mx-auto mb-4 text-destructive" />
          <p className="text-destructive mb-4">{getErrorMessage(error, "Failed to load the single line diagram")}</p>
          <Button onClick={() => refetch()}>Retry</Button>
        </div>
      );
    }
    if (!geometry) {
      return (
        <div className="text-center space-y-4">
          <p className="text-muted-foreground">This site has no single line diagram yet.</p>
          <Button className="gap-2" onClick={startEditing}>
            <Plus className="w-4 h-4" />
            Create diagram
          </Button>
        </div>
      );
    }
    return <SiteSldDiagram geometry={geometry} zoom={zoom} valuesByNode={valuesByNode} editing={editing} />;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Single Line Diagram</h1>
          <p className="text-muted-foreground mt-1">
            {isEditing ? "Editing: click an element to change it, or an empty cell to place one" : "Electrical layout of the site"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isEditing ? (
            <>
              <Button variant="outline" className="gap-2" onClick={cancelEditing} disabled={save.isPending}>
                <X className="w-4 h-4" />
                Cancel
              </Button>
              <Button
                className="gap-2"
                onClick={() => editDraft && save.mutate(editDraft)}
                disabled={!isDirty || errors.length > 0 || save.isPending}
              >
                <Save className="w-4 h-4" />
                {save.isPending ? "Saving..." : "Save"}
              </Button>
            </>
          ) : (
            <>
              <Select value={siteId ?? undefined} onValueChange={(value) => setSearchParams({ siteId: value })}>
                <SelectTrigger className="w-56">
                  <SelectValue placeholder="Select site" />
                </SelectTrigger>
                <SelectContent>
                  {sites.map((site) => (
                    <SelectItem key={site.id} value={site.id}>
                      {site.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="outline" size="icon" onClick={() => refetch()} disabled={!siteId} aria-label="Reload">
                <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
              </Button>
              <Button className="gap-2" onClick={startEditing} disabled={!siteId || isLoading || isError}>
                <Pencil className="w-4 h-4" />
                Manage
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-2" onClick={() => setZoom((previous) => clampZoom(previous + ZOOM_STEP))}>
          <ZoomIn className="w-4 h-4" />Zoom In
        </Button>
        <Button variant="outline" size="sm" className="gap-2" onClick={() => setZoom((previous) => clampZoom(previous - ZOOM_STEP))}>
          <ZoomOut className="w-4 h-4" />Zoom Out
        </Button>
        <Button variant="outline" size="sm" className="gap-2" onClick={fitToScreen} disabled={!geometry}>
          <Maximize2 className="w-4 h-4" />Fit to Screen
        </Button>
        {!isEditing && (
          <Button
            variant={isHandToolActive ? "secondary" : "outline"}
            size="sm"
            className="gap-2"
            onClick={() => setIsHandToolActive((previous) => !previous)}
            aria-pressed={isHandToolActive}
            title="Drag to move around the diagram (or hold Space, or drag with the middle button)"
          >
            <Hand className="w-4 h-4" />Hand Tool
          </Button>
        )}
        <Button
          variant={showValues ? "secondary" : "outline"}
          size="sm"
          className="gap-2"
          onClick={() => setShowValues((previous) => !previous)}
          aria-pressed={showValues}
          title="Show live device values beside the meter, BESS and PV elements"
        >
          <Activity className="w-4 h-4" />Values
        </Button>
        <span className="text-sm text-muted-foreground ml-2">{Math.round(zoom * 100)}%</span>
        {pendingPick && (
          <span className="ml-auto flex items-center gap-2 rounded-md bg-primary/10 px-3 py-1 text-sm text-primary" role="status">
            {pendingPick.label}: click {pendingPick.target === "cell" ? "an empty cell" : "an element or bus"} on the diagram
            <button type="button" className="underline" onClick={() => setPendingPick(null)}>
              cancel
            </button>
          </span>
        )}
      </div>

      {saveError && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          {saveError}
        </p>
      )}

      <div className="flex gap-4" style={{ height: "calc(100vh - 240px)" }}>
        <div
          ref={sldContainerRef}
          className="flex-1 overflow-auto border border-border rounded-lg bg-background select-none"
          style={{ cursor, touchAction: isHandToolActive && !isEditing ? "none" : undefined }}
          {...panHandlers}
        >
          {geometry && !isError ? (
            // margin:auto centers a diagram smaller than the view without blocking scroll when larger.
            <div className="min-w-full min-h-full flex">
              <div className="m-auto">{renderDiagram()}</div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center">{renderDiagram()}</div>
          )}
        </div>
        {editDraft && (
          <SldEditorPanel
            draft={editDraft}
            onChange={changeDraft}
            devices={devices}
            selectedId={selectedId}
            onSelect={setSelectedId}
            selectedCell={selectedCell}
            onClearCell={() => setSelectedCell(null)}
            requestPick={requestPick}
            errors={errors}
          />
        )}
      </div>

      <AlertDialog open={isConfirmingCancel} onOpenChange={setIsConfirmingCancel}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard your changes?</AlertDialogTitle>
            <AlertDialogDescription>The diagram goes back to its last saved version.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction onClick={resetEditState}>Discard</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default SLD;
