import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Hand, Maximize2, RefreshCw, ZoomIn, ZoomOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { sitesApi, sldApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { Site } from "@/api/types/sites";
import type { SiteSldResponse } from "@/api/types/sld";
import { SiteSldDiagram } from "./components/SiteSldDiagram";
import { useDragToPan } from "./hooks/useDragToPan";
import { useWheelZoom } from "./hooks/useWheelZoom";
import { SLD_SVG_SELECTOR, computeSldGeometry } from "./lib/sldGeometry";

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.1;
// Leaves room for the container border so a fitted diagram shows no scrollbars.
const FIT_PADDING = 4;
const clampZoom = (zoom: number) => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));

const SLD = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const siteId = searchParams.get("siteId");
  const [zoom, setZoom] = useState(1);
  const sldContainerRef = useRef<HTMLDivElement>(null);
  const [isHandToolActive, setIsHandToolActive] = useState(true);
  const { cursor, panHandlers } = useDragToPan(sldContainerRef, isHandToolActive);

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
  } = useQuery<SiteSldResponse>({
    queryKey: ["site-sld", siteId],
    queryFn: () => sldApi.getBySite(siteId!),
    enabled: !!siteId,
    retry: false,
  });

  const geometry = useMemo(() => (storedSld ? computeSldGeometry(storedSld.sld) : null), [storedSld]);

  const fitToScreen = useCallback(() => {
    const container = sldContainerRef.current;
    if (!container || !geometry) return;
    const { width, height } = container.getBoundingClientRect();
    if (width === 0 || height === 0) return;
    setZoom(clampZoom(Math.min((width - FIT_PADDING) / geometry.viewBox.width, (height - FIT_PADDING) / geometry.viewBox.height)));
  }, [geometry]);

  // Fit each newly loaded diagram to the available space.
  useLayoutEffect(() => {
    fitToScreen();
  }, [fitToScreen]);

  useWheelZoom(sldContainerRef, SLD_SVG_SELECTOR, zoom, setZoom, clampZoom);

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
    return geometry ? <SiteSldDiagram geometry={geometry} zoom={zoom} /> : null;
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Single Line Diagram</h1>
          <p className="text-muted-foreground mt-1">Electrical layout of the site</p>
        </div>
        <div className="flex items-center gap-3">
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
        <span className="text-sm text-muted-foreground ml-2">{Math.round(zoom * 100)}%</span>
      </div>

      <div
        ref={sldContainerRef}
        className="overflow-auto border border-border rounded-lg bg-background select-none"
        style={{ height: "calc(100vh - 240px)", cursor, touchAction: isHandToolActive ? "none" : undefined }}
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
    </div>
  );
};

export default SLD;
