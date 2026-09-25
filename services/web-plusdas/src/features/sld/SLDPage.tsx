import React, { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { ZoomIn, ZoomOut, Maximize2, RefreshCw, Circle, Zap, Power, Battery, Sun, Wind, Building2, ArrowDownUp, PanelLeftClose, PanelLeftOpen, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MicrogridSLD } from "./components/MicrogridSLD";
import { SummaryCard } from "./components/SummaryCard";
import { fetchCompleteSLDData } from "./lib/sldDataMerger";
import type { SLDData } from "./types";

const SLD = () => {
  const location = useLocation();
  const siteId = location.state?.siteId || "site-001";

  const [sldData, setSldData] = useState<SLDData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSite, setSelectedSite] = useState(siteId || "main");
  const [lastUpdate] = useState(new Date());
  const [zoom, setZoom] = useState(1);
  const [isSummaryCollapsed, setIsSummaryCollapsed] = useState(false);
  const sldContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadSLDData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await fetchCompleteSLDData(siteId);
        setSldData(data);
        if (data.siteId) setSelectedSite(data.siteId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load SLD data");
      } finally {
        setIsLoading(false);
      }
    };
    loadSLDData();
  }, [siteId]);

  const handleRefresh = async () => {
    if (!siteId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchCompleteSLDData(siteId);
      setSldData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh SLD data");
    } finally {
      setIsLoading(false);
    }
  };

  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.1, 3));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.1, 0.3));

  const handleFitToScreen = () => {
    if (!sldContainerRef.current) return;
    const container = sldContainerRef.current;
    const containerRect = container.getBoundingClientRect();
    const scale = Math.min(containerRect.width / 1200, containerRect.height / 800, 1);
    setZoom(scale);
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setZoom(prev => Math.max(0.3, Math.min(3, prev + delta)));
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-screen">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading SLD data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 flex items-center justify-center h-screen">
        <div className="text-center">
          <AlertTriangle className="w-8 h-8 mx-auto mb-4 text-destructive" />
          <p className="text-destructive mb-4">{error}</p>
          <Button onClick={handleRefresh}>Retry</Button>
        </div>
      </div>
    );
  }

  if (!sldData) {
    return (
      <div className="p-6 flex items-center justify-center h-screen">
        <p className="text-muted-foreground">No SLD data available</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Single Line Diagram</h1>
          <p className="text-muted-foreground mt-1">Interactive electrical system visualization</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedSite} onValueChange={setSelectedSite}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Select Diagram" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="main">Main Distribution</SelectItem>
              <SelectItem value="emergency">Emergency System</SelectItem>
              <SelectItem value="solar">Solar Integration</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={handleRefresh}>
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-2" onClick={handleZoomIn}>
          <ZoomIn className="w-4 h-4" />Zoom In
        </Button>
        <Button variant="outline" size="sm" className="gap-2" onClick={handleZoomOut}>
          <ZoomOut className="w-4 h-4" />Zoom Out
        </Button>
        <Button variant="outline" size="sm" className="gap-2" onClick={handleFitToScreen}>
          <Maximize2 className="w-4 h-4" />Fit to Screen
        </Button>
        <div className="flex-1" />
        <Badge variant="outline" className="gap-2">
          <Circle className="w-2 h-2 fill-success text-success" />
          Live Data
        </Badge>
        <span className="text-sm text-muted-foreground">
          Last update: {lastUpdate.toLocaleTimeString()}
        </span>
      </div>

      <div className="flex gap-2 items-stretch" style={{ height: "calc(100vh - 200px)" }}>
        {sldData.summary && sldData.summary.length > 0 && (
          <div className={`border-r border-border transition-all duration-300 ease-in-out flex flex-col ${isSummaryCollapsed ? "w-0 opacity-0" : "w-80"}`}>
            <div className="bg-card border border-border rounded-lg p-4 flex flex-col h-full overflow-hidden">
              <h3 className="text-sm font-semibold text-foreground mb-4 uppercase tracking-wider flex-shrink-0">
                System Summary
              </h3>
              <div className="space-y-3 overflow-y-auto flex-1 pr-2" style={{ scrollbarWidth: "thin", scrollbarColor: "hsl(var(--border)) transparent" }}>
                {sldData.summary.map((item, idx) => {
                  const iconMap: Record<string, React.ReactNode> = {
                    Zap: <Zap className="w-4 h-4" />,
                    Power: <Power className="w-4 h-4" />,
                    Battery: <Battery className="w-4 h-4" />,
                    Sun: <Sun className="w-4 h-4" />,
                    Wind: <Wind className="w-4 h-4" />,
                    Building2: <Building2 className="w-4 h-4" />,
                    ArrowDownUp: <ArrowDownUp className="w-4 h-4" />,
                  };
                  return (
                    <SummaryCard
                      key={idx}
                      label={item.label}
                      value={item.value}
                      subtext={item.subtext}
                      color={item.color}
                      icon={item.icon ? iconMap[item.icon] : undefined}
                      trend={item.trend}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {sldData.summary && sldData.summary.length > 0 && (
          <div className="relative border-r border-border flex flex-col justify-center">
            <Button
              variant="ghost"
              size="icon"
              className="h-12 w-4 rounded-none rounded-r-md border-y border-r border-border -ml-[1px] z-10 bg-background hover:bg-muted"
              onClick={() => setIsSummaryCollapsed(!isSummaryCollapsed)}
            >
              {isSummaryCollapsed ? <PanelLeftOpen className="h-3 w-3" /> : <PanelLeftClose className="h-3 w-3" />}
            </Button>
          </div>
        )}

        <div ref={sldContainerRef} className="flex-1 overflow-auto h-full" onWheel={handleWheel}>
          <div style={{ transform: `scale(${zoom})`, transformOrigin: "top left", display: "inline-block" }}>
            <MicrogridSLD
              data={sldData}
              boundary={{ minX: 0, maxX: 1000, minY: 0, maxY: 800 }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SLD;
