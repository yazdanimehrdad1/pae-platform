import { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Network, TrendingUp, Table, ChevronRight, ChevronDown, Check, PanelLeftClose, PanelLeftOpen, ArrowLeft, Plus, Pencil, Trash2, X, ZoomIn, RotateCcw } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { useHistorianSeries, type TimeWindow } from "./hooks/useHistorianSeries";
import type { TimeRange } from "@/shared/types/api";
import { toast } from "@/shared/hooks/use-toast";
import { useAuth } from "@/shared/contexts/auth";
import { loadTrendsFromStorage, saveTrendsToStorage, type Trend } from "./lib/trendStorage";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from 'recharts';
import { useNotesSidebar } from "@/shared/contexts/NotesSidebarContext";
import { DeviceAssetTree } from "@/shared/components/DeviceAssetTree";
import { useQuery } from "@tanstack/react-query";
import { sitesApi } from "@/api";


const FALLBACK_COLORS = [
  "#8B5CF6", "#F59E0B", "#10B981", "#EF4444", "#3B82F6",
  "#F97316", "#06B6D4", "#84CC16", "#EC4899", "#6366F1",
];

function getColorForPoint(pointName: string): { color: string; type: string } | null {
  const pointPart = pointName.includes(' - ') ? pointName.split(' - ')[1].toLowerCase() : pointName.toLowerCase();
  const fullName = pointName.toLowerCase();

  if (pointPart.includes('real power') || pointPart.includes('kw') || pointPart.includes('mw') || fullName.includes('real power')) return { color: "#22C55E", type: "real-power" };
  if (pointPart.includes('reactive power') || pointPart.includes('kvar') || pointPart.includes('mvar') || fullName.includes('reactive power')) return { color: "#4B5563", type: "reactive-power" };
  if (pointPart.includes('apparent power') || pointPart.includes('kva') || pointPart.includes('mva') || fullName.includes('apparent power')) return { color: "#3B82F6", type: "apparent-power" };
  if (pointPart.includes('temperature') || pointPart.includes('temp') || fullName.includes('temperature')) return { color: "#F97316", type: "temperature" };

  if (pointPart.includes('voltage') || fullName.includes('voltage')) {
    const lp = pointPart.toLowerCase();
    if (lp.includes('voltage va') || (lp.includes('voltage') && lp.includes(' va'))) return { color: "#B91C1C", type: "voltage-va" };
    if (lp.includes('voltage vb') || (lp.includes('voltage') && lp.includes(' vb'))) return { color: "#DC2626", type: "voltage-vb" };
    if (lp.includes('voltage vc') || (lp.includes('voltage') && lp.includes(' vc'))) return { color: "#FCA5A5", type: "voltage-vc" };
    return { color: "#B91C1C", type: "voltage" };
  }

  if (pointPart.includes('current') || fullName.includes('current')) {
    const lp = pointPart.toLowerCase();
    if (lp.includes('current ia') || (lp.includes('current') && lp.includes(' ia'))) return { color: "#6D28D9", type: "current-ia" };
    if (lp.includes('current ib') || (lp.includes('current') && lp.includes(' ib'))) return { color: "#8B5CF6", type: "current-ib" };
    if (lp.includes('current ic') || (lp.includes('current') && lp.includes(' ic'))) return { color: "#C4B5FD", type: "current-ic" };
    return { color: "#6D28D9", type: "current" };
  }

  return null;
}

function getColorsForPoints(selectedPoints: string[]): string[] {
  const colors: (string | null)[] = [];
  const usedColors = new Set<string>();
  const fallbackPool = [...FALLBACK_COLORS];

  selectedPoints.forEach(point => {
    const colorInfo = getColorForPoint(point);
    if (colorInfo && !usedColors.has(colorInfo.color)) {
      colors.push(colorInfo.color);
      usedColors.add(colorInfo.color);
    } else {
      colors.push(null);
    }
  });

  colors.forEach((color, index) => {
    if (!color) {
      let found = false;
      for (const candidateColor of fallbackPool) {
        if (!usedColors.has(candidateColor)) {
          colors[index] = candidateColor;
          usedColors.add(candidateColor);
          found = true;
          break;
        }
      }
      if (!found) {
        let attempts = 0;
        let uniqueColor: string;
        do {
          const hash = selectedPoints[index].split('').reduce((acc, char) => acc + char.charCodeAt(0), index + attempts);
          const hue = (hash * 137.508) % 360;
          uniqueColor = `hsl(${hue}, 70%, 50%)`;
          attempts++;
        } while (usedColors.has(uniqueColor) && attempts < 100);
        colors[index] = uniqueColor;
        usedColors.add(uniqueColor);
      }
    }
  });

  return colors as string[];
}

const PRESET_MS: Record<TimeRange, number> = {
  '1H': 3_600_000, '6H': 6 * 3_600_000, '12H': 12 * 3_600_000,
  '1D': 24 * 3_600_000, '2D': 48 * 3_600_000, '3D': 72 * 3_600_000,
  '1W': 7 * 24 * 3_600_000, '1M': 30 * 24 * 3_600_000, '3M': 90 * 24 * 3_600_000,
};

const PRESET_LABELS: [TimeRange | 'custom', string][] = [
  ['1H', 'Last 1H'], ['6H', 'Last 6H'], ['12H', 'Last 12H'],
  ['1D', 'Last 1D'], ['2D', 'Last 2D'], ['3D', 'Last 3D'],
  ['1W', 'Last Week'], ['1M', 'Last Month'], ['3M', 'Last 3 Months'],
  ['custom', 'Custom range'],
];

function toLocalInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatTimestamp(ts: number, spanMs: number): string {
  const d = new Date(ts);
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (spanMs >= 30 * 24 * 3_600_000) return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + time;
}

function TrendChart({ selectedPoints, timeWindow, pointLabels, siteId }: { selectedPoints: string[]; timeWindow: TimeWindow; pointLabels: Record<string, string>; siteId: string | null }) {
  const { data, isLoading, isError } = useHistorianSeries(siteId, selectedPoints, timeWindow);
  const spanMs = 'preset' in timeWindow
    ? PRESET_MS[timeWindow.preset]
    : new Date(timeWindow.endTime).getTime() - new Date(timeWindow.startTime).getTime();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; timestamp: number } | null>(null);
  const [dragEnd, setDragEnd] = useState<{ x: number; timestamp: number } | null>(null);
  const [zoomRange, setZoomRange] = useState<{ start: number; end: number } | null>(null);

  const chartData = data.map(point => ({ ...point, time: formatTimestamp(point.timestamp, spanMs) }));
  const displayData = zoomRange ? chartData.filter(p => p.timestamp >= zoomRange.start && p.timestamp <= zoomRange.end) : chartData;
  const pointColors = getColorsForPoints(selectedPoints);

  const getTimestampFromX = (x: number, containerWidth: number): number => {
    if (!chartData.length) return 0;
    const index = Math.round((x / containerWidth) * chartData.length);
    return chartData[Math.max(0, Math.min(index, chartData.length - 1))].timestamp;
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!chartContainerRef.current) return;
    const rect = chartContainerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    setIsDragging(true);
    setDragStart({ x, timestamp: getTimestampFromX(x, rect.width) });
    setDragEnd(null);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !dragStart || !chartContainerRef.current) return;
    const rect = chartContainerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    setDragEnd({ x, timestamp: getTimestampFromX(x, rect.width) });
  };

  const handleMouseUp = () => {
    if (!isDragging || !dragStart) return;
    if (dragEnd) {
      const startTime = Math.min(dragStart.timestamp, dragEnd.timestamp);
      const endTime = Math.max(dragStart.timestamp, dragEnd.timestamp);
      if (Math.abs(endTime - startTime) > 60000) setZoomRange({ start: startTime, end: endTime });
    }
    setIsDragging(false);
    setDragStart(null);
    setDragEnd(null);
  };

  const selectionRect = isDragging && dragStart && dragEnd && chartContainerRef.current
    ? { left: Math.min(dragStart.x, dragEnd.x), width: Math.abs(dragEnd.x - dragStart.x), top: 0, height: chartContainerRef.current.getBoundingClientRect().height }
    : null;

  if (isLoading) return <div className="h-[28rem] flex items-center justify-center"><div className="text-muted-foreground">Loading trend data...</div></div>;
  if (isError) return <div className="h-[28rem] flex items-center justify-center"><div className="text-destructive text-sm">Failed to load trend data</div></div>;
  if (!isLoading && data.length === 0 && selectedPoints.length > 0) return <div className="h-[28rem] flex items-center justify-center"><div className="text-muted-foreground text-sm">No data available in the selected time range</div></div>;

  return (
    <div className="space-y-2">
      {zoomRange && (
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => setZoomRange(null)} className="gap-2">
            <RotateCcw className="w-4 h-4" />Reset Zoom
          </Button>
        </div>
      )}
      <div
        ref={chartContainerRef}
        className="h-[28rem] relative cursor-crosshair select-none"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {selectionRect && (
          <div
            className="absolute bg-primary/20 border-2 border-primary pointer-events-none z-10"
            style={{ left: `${selectionRect.left}px`, width: `${selectionRect.width}px`, top: `${selectionRect.top}px`, height: `${selectionRect.height}px` }}
          />
        )}
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={displayData} margin={{ top: 5, right: 40, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} interval={displayData.length > 20 ? Math.floor(displayData.length / 10) : 0} />
            <YAxis tick={{ fontSize: 12 }} />
            <RechartsTooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px' }} />
            <Legend wrapperStyle={{ paddingTop: '20px' }} iconType="line" formatter={(value) => value.includes(' - ') ? value.replace(' - ', '-') : value} />
            {selectedPoints.map((point, index) => (
              <Line key={point} type="monotone" dataKey={point} stroke={pointColors[index]} strokeWidth={2} dot={false} name={pointLabels[point] ?? point} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function Historian() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { isNotesCollapsed, setIsNotesCollapsed } = useNotesSidebar();
  const [trends, setTrends] = useState<Trend[]>([]);
  const [currentTrendId, setCurrentTrendId] = useState<string>('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const previousSidebarStateRef = useRef<boolean | null>(null);
  const previousNotesStateRef = useRef<boolean | null>(null);

  useEffect(() => {
    if (!isNotesCollapsed) {
      if (previousSidebarStateRef.current === null) previousSidebarStateRef.current = isSidebarOpen;
      setIsSidebarOpen(false);
    } else {
      if (previousSidebarStateRef.current !== null) {
        setIsSidebarOpen(previousSidebarStateRef.current);
        previousSidebarStateRef.current = null;
      }
    }
  }, [isNotesCollapsed]);

  const handleTrendsPanelToggle = () => {
    if (!isSidebarOpen && !isNotesCollapsed) {
      if (previousNotesStateRef.current === null) previousNotesStateRef.current = isNotesCollapsed;
      setIsNotesCollapsed(true);
      setIsSidebarOpen(true);
    } else if (isSidebarOpen && previousNotesStateRef.current !== null) {
      setIsNotesCollapsed(previousNotesStateRef.current);
      previousNotesStateRef.current = null;
      setIsSidebarOpen(false);
    } else {
      setIsSidebarOpen(!isSidebarOpen);
    }
  };

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [newTrendName, setNewTrendName] = useState('');
  const [editingTrendId, setEditingTrendId] = useState<string | null>(null);
  const [editingTrendName, setEditingTrendName] = useState('');
  const [deletingTrendId, setDeletingTrendId] = useState<string | null>(null);
  const [draggedTrendId, setDraggedTrendId] = useState<string | null>(null);
  const [layoutCount, setLayoutCount] = useState<number>(1);
  const [timeRange, setTimeRange] = useState<TimeRange | 'custom'>('1H');
  const [customStart, setCustomStart] = useState<string>(() => toLocalInput(new Date(Date.now() - 3_600_000)));
  const [customEnd, setCustomEnd] = useState<string>(() => toLocalInput(new Date()));
  const [topTrendId, setTopTrendId] = useState<string | null>(null);
  const [middleTrendId, setMiddleTrendId] = useState<string | null>(null);
  const [bottomTrendId, setBottomTrendId] = useState<string | null>(null);
  const [fourthTrendId, setFourthTrendId] = useState<string | null>(null);
  const [isCollectionExpanded, setIsCollectionExpanded] = useState<boolean>(true);
  const [isSharedExpanded, setIsSharedExpanded] = useState<boolean>(true);
  const [selectedSiteId, setSelectedSiteId] = useState<string>('');

  const { data: sites = [] } = useQuery({
    queryKey: ['sites'],
    queryFn: sitesApi.getAll,
  });

  useEffect(() => {
    if (selectedSiteId || sites.length === 0) return;
    const stateSiteId = location.state?.selectedSite?.id;
    setSelectedSiteId(stateSiteId && sites.some(s => s.id === stateSiteId) ? stateSiteId : sites[0].id);
  }, [sites, selectedSiteId, location.state]);

  const selectedSite = sites.find(site => site.id === selectedSiteId);

  const previousSiteIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedSiteId) return;
    if (previousSiteIdRef.current && previousSiteIdRef.current !== selectedSiteId) {
      setTrends(prev => prev.map(t => ({ ...t, points: [] })));
      setPointLabels({});
    }
    previousSiteIdRef.current = selectedSiteId;
  }, [selectedSiteId]);

  const timeWindow: TimeWindow = timeRange === 'custom'
    ? { startTime: new Date(customStart).toISOString(), endTime: new Date(customEnd).toISOString() }
    : { preset: timeRange };

  const topTrendRef = useRef<HTMLDivElement>(null);
  const middleTrendRef = useRef<HTMLDivElement>(null);
  const bottomTrendRef = useRef<HTMLDivElement>(null);
  const fourthTrendRef = useRef<HTMLDivElement>(null);
  const cardContentRef = useRef<HTMLDivElement>(null);

  const sites_saved_trends = trends;
  const shared_trends: Trend[] = [];

  const handleToggleCollectionTrend = (trendId: string) => {
    if (currentTrendId === trendId) setCurrentTrendId('');
    else { setCurrentTrendId(trendId); scrollToTrend(trendId); }
  };

  const currentTrend = currentTrendId ? trends.find(t => t.id === currentTrendId) || null : null;
  const selectedPoints = currentTrend?.points || [];

  const lastDataTimeString = selectedPoints.length > 0
    ? new Date().toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : 'No data';

  useEffect(() => {
    if (user?.id) {
      const loadedTrends = loadTrendsFromStorage(user.id);
      setTrends(loadedTrends);
      if (loadedTrends.length > 0) {
        setCurrentTrendId(loadedTrends[0].id);
        setTopTrendId(prev => prev || loadedTrends[0].id);
        setMiddleTrendId(prev => prev || (loadedTrends.length > 1 ? loadedTrends[1].id : null));
        setBottomTrendId(prev => prev || (loadedTrends.length > 2 ? loadedTrends[2].id : null));
        setFourthTrendId(prev => prev || (loadedTrends.length > 3 ? loadedTrends[3].id : null));
      }
    }
  }, [user?.id]);

  useEffect(() => {
    if (trends.length > 0) {
      const n = trends.length;
      if (layoutCount === 1) { if (!topTrendId) setTopTrendId(currentTrendId || trends[0].id); setMiddleTrendId(null); setBottomTrendId(null); setFourthTrendId(null); }
      else if (layoutCount === 2) { setTopTrendId(trends[0].id); setMiddleTrendId(n > 1 ? trends[1].id : null); setBottomTrendId(null); setFourthTrendId(null); }
      else if (layoutCount === 3) { setTopTrendId(trends[0].id); setMiddleTrendId(n > 1 ? trends[1].id : null); setBottomTrendId(n > 2 ? trends[2].id : null); setFourthTrendId(null); }
      else { setTopTrendId(trends[0].id); setMiddleTrendId(n > 1 ? trends[1].id : null); setBottomTrendId(n > 2 ? trends[2].id : null); setFourthTrendId(n > 3 ? trends[3].id : null); }
    } else { setTopTrendId(null); setMiddleTrendId(null); setBottomTrendId(null); setFourthTrendId(null); }
  }, [layoutCount, trends]);

  useEffect(() => { if (user?.id && trends.length > 0) saveTrendsToStorage(user.id, trends); }, [trends, user?.id]);

  const [pointLabels, setPointLabels] = useState<Record<string, string>>({});

  const updateCurrentTrendPoints = (points: string[], labels: Record<string, string>) => {
    setPointLabels(prev => ({ ...prev, ...labels }));
    setTrends(prev => prev.map(trend => trend.id === currentTrendId ? { ...trend, points } : trend));
  };

  const handleResolveLabels = (labels: Record<string, string>) => {
    setPointLabels(prev => ({ ...prev, ...labels }));
  };

  const scrollToTrend = (trendId: string) => {
    let targetRef: React.RefObject<HTMLDivElement> | null = null;
    if (topTrendId === trendId) targetRef = topTrendRef;
    else if (middleTrendId === trendId) targetRef = middleTrendRef;
    else if (bottomTrendId === trendId) targetRef = bottomTrendRef;
    else if (fourthTrendId === trendId) targetRef = fourthTrendRef;

    if (targetRef?.current && cardContentRef.current) {
      const containerRect = cardContentRef.current.getBoundingClientRect();
      const targetRect = targetRef.current.getBoundingClientRect();
      const scrollTop = cardContentRef.current.scrollTop;
      cardContentRef.current.scrollTo({ top: targetRect.top - containerRect.top + scrollTop - 20, behavior: 'smooth' });
    }
  };

  const handleCreateTrend = () => {
    const trimmedName = newTrendName.trim();
    if (!trimmedName) { toast({ title: "Invalid Trend Name", description: "Trend name cannot be empty.", variant: "destructive" }); return; }
    if (trimmedName.length > 15) { toast({ title: "Trend Name Too Long", description: "Trend name cannot exceed 15 characters.", variant: "destructive" }); return; }
    if (trends.length >= 4) { toast({ title: "Maximum Trends Reached", description: "You can have a maximum of 4 trends.", variant: "destructive" }); return; }

    const newTrend: Trend = { id: Date.now().toString(), name: trimmedName, points: [] };
    setTrends(prev => [...prev, newTrend]);
    setCurrentTrendId(newTrend.id);
    setNewTrendName('');
    setIsCreateDialogOpen(false);
    toast({ title: "Trend Created", description: `Trend "${trimmedName}" has been created successfully.` });
  };

  const handleEditTrend = (trendId: string) => {
    const trend = trends.find(t => t.id === trendId);
    if (trend) { setEditingTrendId(trendId); setEditingTrendName(trend.name); setIsEditDialogOpen(true); }
  };

  const handleSaveEdit = () => {
    const trimmedName = editingTrendName.trim();
    if (!trimmedName) { toast({ title: "Invalid Trend Name", description: "Trend name cannot be empty.", variant: "destructive" }); return; }
    if (trimmedName.length > 15) { toast({ title: "Trend Name Too Long", description: "Trend name cannot exceed 15 characters.", variant: "destructive" }); return; }
    if (editingTrendId) {
      setTrends(prev => prev.map(trend => trend.id === editingTrendId ? { ...trend, name: trimmedName } : trend));
      toast({ title: "Trend Updated", description: `Trend name has been updated to "${trimmedName}".` });
      setIsEditDialogOpen(false);
      setEditingTrendId(null);
      setEditingTrendName('');
    }
  };

  const handleDeleteTrend = (trendId: string) => {
    const trend = trends.find(t => t.id === trendId);
    if (trend) { setDeletingTrendId(trendId); setIsDeleteDialogOpen(true); }
  };

  const handleConfirmDelete = () => {
    if (deletingTrendId) {
      const trend = trends.find(t => t.id === deletingTrendId);
      const trendName = trend?.name || 'Trend';
      const isDeletingCurrent = currentTrendId === deletingTrendId;
      setTrends(prev => {
        const updated = prev.filter(t => t.id !== deletingTrendId);
        if (isDeletingCurrent && updated.length > 0) setCurrentTrendId(updated[0].id);
        return updated;
      });
      toast({ title: "Trend Deleted", description: `Trend "${trendName}" has been deleted.` });
      setIsDeleteDialogOpen(false);
      setDeletingTrendId(null);
    }
  };

  const handleClearTrendPoints = (trendId: string) => {
    const trend = trends.find(t => t.id === trendId);
    if (trend) {
      setTrends(prev => prev.map(t => t.id === trendId ? { ...t, points: [] } : t));
      toast({ title: "Points Cleared", description: `All points have been removed from "${trend.name}".` });
    }
  };

  const handleDragStart = (e: React.DragEvent, trendId: string) => {
    setDraggedTrendId(trendId);
    e.dataTransfer.effectAllowed = 'move';
    if (e.currentTarget instanceof HTMLElement) e.currentTarget.style.opacity = '0.5';
  };

  const handleDragEnd = (e: React.DragEvent) => {
    if (e.currentTarget instanceof HTMLElement) e.currentTarget.style.opacity = '1';
    setDraggedTrendId(null);
  };

  const handleDrop = (e: React.DragEvent, targetTrendId: string) => {
    e.preventDefault();
    if (!draggedTrendId || draggedTrendId === targetTrendId) return;
    setTrends(prev => {
      const newTrends = [...prev];
      const draggedIndex = newTrends.findIndex(t => t.id === draggedTrendId);
      const targetIndex = newTrends.findIndex(t => t.id === targetTrendId);
      if (draggedIndex === -1 || targetIndex === -1) return prev;
      const [draggedItem] = newTrends.splice(draggedIndex, 1);
      newTrends.splice(targetIndex, 0, draggedItem);
      return newTrends;
    });
    setDraggedTrendId(null);
  };


  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Historian</h1>
            <p className="text-muted-foreground mt-1">Time-series data analysis and trending</p>
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" size="sm" onClick={() => {
              if (location.state?.selectedSite) navigate('/site-devices', { state: { selectedSite: location.state.selectedSite } });
              else navigate('/sites');
            }}>
              <ArrowLeft className="w-4 h-4 mr-2" />Back to Devices
            </Button>
            <Badge variant="outline" className="bg-success/10 text-success border-success">Last: {lastDataTimeString}</Badge>
            <Button variant="outline" size="sm">Export Data</Button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className={`border-r border-border transition-all duration-300 ease-in-out flex flex-col ${isSidebarOpen ? 'w-80' : 'w-0 opacity-0'}`}>
          <div className="flex-1 overflow-hidden min-w-[20rem] flex flex-col">
            <div className="shrink-0 border-b border-border px-4 py-3">
              <h2 className="text-lg font-semibold text-foreground">Trends Panel</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
              <section>
                <h3 className="text-sm font-medium text-foreground mb-2">Saved trends</h3>
                <div className="rounded-md border border-border bg-card overflow-hidden p-3">
                  <button type="button" onClick={() => setIsCollectionExpanded(p => !p)} className="w-full flex items-center justify-between py-1 px-2 rounded cursor-pointer hover:bg-muted/50">
                    <div className="flex items-center gap-1">
                      {isCollectionExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      <span className="text-sm font-semibold">Collection</span>
                    </div>
                  </button>
                  {isCollectionExpanded && (
                    <div className="mt-1">
                      {sites_saved_trends.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No saved trends yet. Create one using the controls above.</p>
                      ) : (
                        <div className="space-y-1">
                          {sites_saved_trends.map(trend => (
                            <div key={trend.id} role="button" tabIndex={0}
                              onClick={() => handleToggleCollectionTrend(trend.id)}
                              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleToggleCollectionTrend(trend.id); }}
                              className={`w-full flex items-center gap-2 px-2 py-1 rounded text-sm text-left cursor-pointer hover:bg-muted/60 ${currentTrendId === trend.id ? "bg-muted" : ""}`}>
                              <Checkbox checked={currentTrendId === trend.id} className="mr-1 pointer-events-none" />
                              <span className={`truncate ${currentTrendId === trend.id ? "font-medium" : ""}`}>{trend.name}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </section>
              <section>
                <div className="rounded-md border border-border bg-card overflow-hidden p-3">
                  <button type="button" onClick={() => setIsSharedExpanded(p => !p)} className="w-full flex items-center justify-between py-1 px-2 rounded cursor-pointer hover:bg-muted/50">
                    <div className="flex items-center gap-1">
                      {isSharedExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      <span className="text-sm font-semibold">Shared</span>
                    </div>
                  </button>
                  {isSharedExpanded && <div className="mt-1"><p className="text-xs text-muted-foreground">No shared trends yet.</p></div>}
                </div>
              </section>
              <section className="space-y-2">
                <h3 className="text-sm font-medium text-foreground mb-2">Asset tree</h3>
                <div className="space-y-1">
                  <Label htmlFor="historian-site" className="text-xs text-muted-foreground">Site</Label>
                  <Select value={selectedSiteId} onValueChange={setSelectedSiteId}>
                    <SelectTrigger id="historian-site" className="h-8 text-sm"><SelectValue placeholder="Select a site" /></SelectTrigger>
                    <SelectContent>
                      {sites.map(site => <SelectItem key={site.id} value={site.id}>{site.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <DeviceAssetTree
                  siteId={selectedSiteId || null}
                  siteName={selectedSite?.name ?? 'Site'}
                  selectedPoints={selectedPoints}
                  onSelect={updateCurrentTrendPoints}
                  onResolveLabels={handleResolveLabels}
                  pointIdsToResolve={trends.flatMap(t => t.points)}
                />
              </section>
            </div>
          </div>
        </div>

        <div className="relative border-r border-border flex flex-col justify-center">
          <Button variant="ghost" size="icon" className="h-12 w-4 rounded-none rounded-r-md border-y border-r border-border -ml-[1px] z-10 bg-background hover:bg-muted" onClick={handleTrendsPanelToggle}>
            {isSidebarOpen ? <PanelLeftClose className="h-3 w-3" /> : <PanelLeftOpen className="h-3 w-3" />}
          </Button>
        </div>

        <div className="flex-1 flex flex-col">
          {selectedPoints.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-6">
              <div className="w-16 h-16 bg-muted/50 rounded-full flex items-center justify-center mb-4">
                <Network className="w-8 h-8 opacity-50" />
              </div>
              <h3 className="text-lg font-semibold mb-2">No Device Selected</h3>
              <p className="max-w-sm text-center">Select a data point from the Asset tree in the Trends Panel to view historical trends.</p>
            </div>
          ) : (
            <div className="h-full flex flex-col">
              <div className="border-b border-border px-6 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2 flex-1 overflow-x-auto">
                    {trends.map(trend => (
                      <div key={trend.id} draggable onDragStart={(e) => handleDragStart(e, trend.id)} onDragEnd={handleDragEnd} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; }} onDrop={(e) => handleDrop(e, trend.id)}
                        className={`flex items-center gap-1 rounded-md border cursor-move transition-opacity ${currentTrendId === trend.id ? "bg-primary text-primary-foreground border-primary" : "bg-background border-border"} ${draggedTrendId === trend.id ? "opacity-50" : ""}`}>
                        <Button variant="ghost" size="sm" onClick={() => { setCurrentTrendId(trend.id); scrollToTrend(trend.id); }}
                          className={`flex items-center gap-2 whitespace-nowrap h-8 ${currentTrendId === trend.id ? "text-primary-foreground hover:bg-primary/90" : "hover:bg-muted"}`}>
                          <TrendingUp className="w-4 h-4" />{trend.name}
                        </Button>
                        <div className="flex items-center pr-1">
                          {[
                            { icon: <X className="w-3 h-3" />, onClick: () => handleClearTrendPoints(trend.id), disabled: trend.points.length === 0, tooltip: "Clear all points" },
                            { icon: <Pencil className="w-3 h-3" />, onClick: () => handleEditTrend(trend.id), disabled: false, tooltip: "Edit trend name" },
                            { icon: <Trash2 className="w-3 h-3" />, onClick: () => handleDeleteTrend(trend.id), disabled: false, tooltip: "Delete trend" },
                          ].map((action, i) => (
                            <TooltipProvider key={i}>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button variant="ghost" size="icon" className={`h-6 w-6 ${currentTrendId === trend.id ? "text-primary-foreground hover:bg-primary/80" : "hover:bg-muted"}`}
                                    onClick={(e) => { e.stopPropagation(); action.onClick(); }} disabled={action.disabled}>
                                    {action.icon}
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent><p>{action.tooltip}</p></TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-2">
                    <Select value={currentTrendId} onValueChange={setCurrentTrendId}>
                      <SelectTrigger className="w-[200px]"><SelectValue placeholder="Select a trend" /></SelectTrigger>
                      <SelectContent>{trends.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                    </Select>
                    <div className="flex items-center gap-2">
                      <Label htmlFor="layout-count">Layout</Label>
                      <Select value={layoutCount.toString()} onValueChange={(v) => setLayoutCount(Number(v))}>
                        <SelectTrigger className="w-[120px]" id="layout-count"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {[1, 2, 3, 4].map(n => <SelectItem key={n} value={n.toString()}>{n} Trend{n > 1 ? 's' : ''}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </div>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span>
                            <Button size="sm" onClick={() => setIsCreateDialogOpen(true)} className="gap-2" disabled={trends.length >= 4}>
                              <Plus className="w-4 h-4" />New Trend
                            </Button>
                          </span>
                        </TooltipTrigger>
                        {trends.length >= 4 && <TooltipContent><p>Maximum of 4 trends reached.</p></TooltipContent>}
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </div>
              </div>

              <div className="flex-1 p-6 overflow-y-auto">
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-end">
                      <div className="flex flex-col items-end gap-2">
                        <div className="flex items-center gap-2">
                          <Label htmlFor="time-range">Time Range</Label>
                          <Select value={timeRange} onValueChange={(v) => setTimeRange(v as TimeRange | 'custom')}>
                            <SelectTrigger className="w-[160px]" id="time-range"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {PRESET_LABELS.map(([v, label]) => (
                                <SelectItem key={v} value={v}>{label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        {timeRange === 'custom' && (
                          <div className="flex items-center gap-2">
                            <Input type="datetime-local" value={customStart} onChange={e => setCustomStart(e.target.value)} className="w-[180px]" />
                            <span className="text-muted-foreground text-sm">to</span>
                            <Input type="datetime-local" value={customEnd} onChange={e => setCustomEnd(e.target.value)} className="w-[180px]" />
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground flex items-center gap-1">
                          <ZoomIn className="w-3 h-3" /><span>Drag to zoom</span>
                        </div>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent ref={cardContentRef}>
                    <div className="space-y-6">
                      {layoutCount >= 1 && topTrendId && (
                        <div ref={topTrendRef} className="border rounded-lg p-4 bg-card space-y-2">
                          <div className="flex items-center justify-between">
                            <Label>Trend-1: {trends.find(t => t.id === topTrendId)?.name || ''}</Label>
                            {layoutCount === 1 && (
                              <Select value={topTrendId} onValueChange={(v) => setTopTrendId(v)}>
                                <SelectTrigger className="w-[200px]"><SelectValue /></SelectTrigger>
                                <SelectContent>{trends.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                              </Select>
                            )}
                          </div>
                          <TrendChart selectedPoints={trends.find(t => t.id === topTrendId)?.points || []} timeWindow={timeWindow} pointLabels={pointLabels} siteId={selectedSiteId || null} />
                        </div>
                      )}
                      {layoutCount >= 2 && middleTrendId && (
                        <div ref={middleTrendRef} className="border rounded-lg p-4 bg-card space-y-2">
                          <Label>Trend-2: {trends.find(t => t.id === middleTrendId)?.name || ''}</Label>
                          <TrendChart selectedPoints={trends.find(t => t.id === middleTrendId)?.points || []} timeWindow={timeWindow} pointLabels={pointLabels} siteId={selectedSiteId || null} />
                        </div>
                      )}
                      {layoutCount >= 3 && bottomTrendId && (
                        <div ref={bottomTrendRef} className="border rounded-lg p-4 bg-card space-y-2">
                          <Label>Trend-3: {trends.find(t => t.id === bottomTrendId)?.name || ''}</Label>
                          <TrendChart selectedPoints={trends.find(t => t.id === bottomTrendId)?.points || []} timeWindow={timeWindow} pointLabels={pointLabels} siteId={selectedSiteId || null} />
                        </div>
                      )}
                      {layoutCount >= 4 && fourthTrendId && (
                        <div ref={fourthTrendRef} className="border rounded-lg p-4 bg-card space-y-2">
                          <Label>Trend-4: {trends.find(t => t.id === fourthTrendId)?.name || ''}</Label>
                          <TrendChart selectedPoints={trends.find(t => t.id === fourthTrendId)?.points || []} timeWindow={timeWindow} pointLabels={pointLabels} siteId={selectedSiteId || null} />
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </div>
      </div>

      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Trend</DialogTitle>
            <DialogDescription>Give your trend a name. Maximum 15 characters, up to 4 trends ({trends.length}/4 used).</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="trend-name">Trend Name</Label>
                <span className={`text-xs ${newTrendName.length > 15 ? 'text-destructive' : 'text-muted-foreground'}`}>{newTrendName.length}/15</span>
              </div>
              <Input id="trend-name" placeholder="e.g., Power Analysis" value={newTrendName}
                onChange={(e) => { if (e.target.value.length <= 15) setNewTrendName(e.target.value); }} maxLength={15}
                onKeyDown={(e) => { if (e.key === 'Enter' && newTrendName.trim() && newTrendName.length <= 15 && trends.length < 4) handleCreateTrend(); }} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setIsCreateDialogOpen(false); setNewTrendName(''); }}>Cancel</Button>
            <Button onClick={handleCreateTrend} disabled={!newTrendName.trim() || newTrendName.length > 15 || trends.length >= 4}>Create Trend</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Trend</DialogTitle>
            <DialogDescription>Update the name of your trend. Maximum 15 characters.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="edit-trend-name">Trend Name</Label>
                <span className={`text-xs ${editingTrendName.length > 15 ? 'text-destructive' : 'text-muted-foreground'}`}>{editingTrendName.length}/15</span>
              </div>
              <Input id="edit-trend-name" value={editingTrendName}
                onChange={(e) => { if (e.target.value.length <= 15) setEditingTrendName(e.target.value); }} maxLength={15}
                onKeyDown={(e) => { if (e.key === 'Enter' && editingTrendName.trim()) handleSaveEdit(); if (e.key === 'Escape') { setIsEditDialogOpen(false); setEditingTrendId(null); setEditingTrendName(''); } }} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setIsEditDialogOpen(false); setEditingTrendId(null); setEditingTrendName(''); }}>Cancel</Button>
            <Button onClick={handleSaveEdit} disabled={!editingTrendName.trim() || editingTrendName.length > 15}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Trend</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete "{trends.find(t => t.id === deletingTrendId)?.name}"? This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => { setIsDeleteDialogOpen(false); setDeletingTrendId(null); }}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
