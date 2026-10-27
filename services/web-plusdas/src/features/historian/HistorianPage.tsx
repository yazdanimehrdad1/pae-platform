import { useState, useEffect, useMemo, useRef } from "react";
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
import { Network, TrendingUp, Table, ChevronRight, ChevronDown, Check, PanelLeftClose, PanelLeftOpen, ArrowLeft, Plus, Pencil, Trash2, X, ZoomIn, RotateCcw, Maximize2, Minimize2, Smartphone } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { useHistorianSeries } from "./hooks/useHistorianSeries";
import type { LinePoint } from "./sampling/chartRows";
import { latestAtOrBefore } from "./sampling/tooltip";
import type { ChartRow, TimeWindow, Trend } from "./types";
import type { TimeRange } from "@/api/types/historian";
import { toast } from "@/shared/hooks/use-toast";
import { useAuth } from "@/shared/contexts/auth";
import { loadTrendsFromStorage, saveTrendsToStorage } from "./lib/trendStorage";
import { loadDiscreteMode, saveDiscreteMode } from "./lib/discreteModeStorage";
import { describeDiscreteSeries } from "./lib/discreteSeries";
import { usePointCatalog } from "./hooks/usePointCatalog";
import { DEFAULT_DISCRETE_MODE, type DiscreteModeId } from "./components/discrete/discreteModes";
import { DiscreteModeToggle } from "./components/discrete/DiscreteModeToggle";
import { AutoRefreshToggle } from "./components/AutoRefreshToggle";
import { AxisGroupedLegend } from "./components/AxisGroupedLegend";
import { AxisScaleToggle } from "./components/AxisScaleToggle";
import { assignAxes, axisWidth, DEFAULT_AXIS_SCALE, UNIT_AXIS_COLORS, valueRange, type AxisScale } from "./lib/axes";
import { useTheme } from "@/shared/components/theme-provider";
import { parseForecastSelectionId, parseFunctionSelectionId, parseSelectionId } from "@/shared/lib/discretePoints";
import { FORECAST_AHEAD_HOURS, PRESET_MS, type ForecastAheadHours } from "./lib/timeWindows";
import { RefreshReadingsButton } from "./components/RefreshReadingsButton";
import { StateLanes } from "./components/discrete/StateLanes";
import { buildStepLayout, renderStepSeries, STATE_AXIS_WIDTH } from "./components/discrete/stepSeries";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from 'recharts';
import { useNotesSidebar } from "@/shared/contexts/NotesSidebarContext";
import { useBreakpoint } from "@/shared/hooks/use-mobile";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { DeviceAssetTree, type RevealRequest } from "@/shared/components/DeviceAssetTree";
import { useQuery } from "@tanstack/react-query";
import { sitesApi } from "@/api";
import { TimeZoneToggle } from "@/shared/components/TimeZoneToggle";
import { useDisplayTimeZone } from "@/shared/hooks/useDisplayTimeZone";
import { fromZonedInput, toZonedInput } from "@/shared/lib/zonedTime";
import { SeriesStylePopover } from "./components/SeriesStylePopover";
import { latestReadingTime } from "./lib/latestReading";
import { DASH_ARRAY, pruneSeriesStyles, resolveSeriesStyles, type SeriesStyle } from "./lib/seriesStyles";

const PRESET_LABELS: [TimeRange | 'custom', string][] = [
  ['1H', 'Last 1H'], ['6H', 'Last 6H'], ['12H', 'Last 12H'],
  ['1D', 'Last 1D'], ['2D', 'Last 2D'], ['3D', 'Last 3D'],
  ['1W', 'Last Week'], ['1M', 'Last Month'], ['3M', 'Last 3 Months'],
  ['custom', 'Custom range'],
];

// Chart times are in the display zone: the site's, or the user's own (useDisplayTimeZone).
function formatTimestamp(ts: number, spanMs: number, timeZone: string): string {
  const d = new Date(ts);
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone });
  if (spanMs >= 30 * 24 * 3_600_000) return d.toLocaleDateString([], { month: 'short', day: 'numeric', timeZone });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', timeZone }) + ' ' + time;
}

// The right margin keeps the last time tick from being clipped; on phones the ticks are short.
const CHART_MARGIN = { top: 5, right: 40, left: 0, bottom: 5 };
const PHONE_CHART_MARGIN = { ...CHART_MARGIN, right: 16 };

// Time-axis ticks on a phone: a narrow chart fits a few short labels, so the time alone within two
// days and the date alone beyond (the tooltip still shows both).
function formatPhoneTick(ts: number, spanMs: number, timeZone: string): string {
  const d = new Date(ts);
  if (spanMs < 2 * 24 * 3_600_000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', timeZone });
}

type StepLayout = ReturnType<typeof buildStepLayout>;

// The hovered time, each analog line's latest sample at or before it (looked up in the line's own
// samples, since lines don't share timestamps), and the step series' states.
function TrendTooltip({ active, label, payload, lines, analogKeys, pointLabels, colorByKey, formatTime, stepLayout }: {
  active?: boolean;
  label?: number;
  payload?: Array<{ dataKey?: string | number; name?: string; value?: number; color?: string }>;
  lines: Record<string, LinePoint[]>;
  analogKeys: string[];
  pointLabels: Record<string, string>;
  colorByKey: Map<string, string>;
  formatTime: (timestamp: number) => string;
  stepLayout: StepLayout;
}) {
  if (!active || typeof label !== 'number') return null;
  const analog = analogKeys
    .map(key => ({ key, value: latestAtOrBefore(lines[key] ?? [], key, label) }))
    .filter(entry => entry.value !== null);
  const steps = (payload ?? []).filter(item => !analogKeys.includes(String(item.dataKey)) && item.value != null);
  if (analog.length === 0 && steps.length === 0) return null;
  return (
    <div className="rounded-lg border border-border bg-card p-2 text-sm shadow-sm">
      <div className="mb-1 font-medium">{formatTime(label)}</div>
      {analog.map(({ key, value }) => (
        <div key={key} style={{ color: colorByKey.get(key) }}>{pointLabels[key] ?? key}: {value}</div>
      ))}
      {steps.map(item => (
        <div key={String(item.dataKey)} style={{ color: item.color }}>{item.name}: {stepLayout?.tooltipLabel(item.dataKey, item.value) ?? item.value}</div>
      ))}
    </div>
  );
}

function TrendChart({ selectedPoints, timeWindow, timeZone, autoRefresh, forecastAheadHours, scale, onScaleChange, styles, onStylesChange, pointLabels, siteId, discreteMode, onDiscreteModeChange, onRevealPoint, onLatestReading }: {
  selectedPoints: string[];
  timeWindow: TimeWindow;
  timeZone: string;
  autoRefresh: boolean;
  /** How far past now a preset window's PV forecast reaches (0 = up to now). */
  forecastAheadHours: number;
  /** How the analog lines share vertical axes; saved on the trend. */
  scale: AxisScale;
  onScaleChange: (scale: AxisScale) => void;
  /** What the user changed in each line's colour, style and width; saved on the trend. */
  styles: Record<string, SeriesStyle> | undefined;
  onStylesChange: (styles: Record<string, SeriesStyle> | undefined) => void;
  pointLabels: Record<string, string>;
  siteId: string | null;
  discreteMode: DiscreteModeId;
  onDiscreteModeChange: (mode: DiscreteModeId) => void;
  // A series name was clicked: show that selection in the Trends panel.
  onRevealPoint: (selectionId: string) => void;
  /** The newest device reading of the trend's window (null: none), after every fetch. */
  onLatestReading: (timestamp: number | null) => void;
}) {
  const [zoomRange, setZoomRange] = useState<{ start: number; end: number } | null>(null);
  // The window the chart shows is fetched: zooming in refetches, so a zoom of 3 days or less gets
  // every reading again (see sampling/README.md).
  const viewWindow: TimeWindow = zoomRange
    ? { startTime: new Date(zoomRange.start).toISOString(), endTime: new Date(zoomRange.end).toISOString() }
    : timeWindow;
  const { data, lines, functionSeries, forecastSeries, isLoading, isFetching, isError } = useHistorianSeries(siteId, selectedPoints, viewWindow, { autoRefresh, forecastAheadHours });
  const { pointsById } = usePointCatalog(siteId);
  // Zoomed, the fetched window is the zoomed one, so its newest reading says nothing about how live
  // the data is: the page keeps the last one reported for the whole window (and while loading).
  const latestReading = useMemo(() => latestReadingTime(lines, selectedPoints), [lines, selectedPoints]);
  useEffect(() => {
    if (!zoomRange && !isLoading) onLatestReading(latestReading);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestReading, zoomRange, isLoading]);
  const spanMs = 'preset' in timeWindow
    ? PRESET_MS[timeWindow.preset]
    : new Date(timeWindow.endTime).getTime() - new Date(timeWindow.startTime).getTime();
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; timestamp: number } | null>(null);
  const [dragEnd, setDragEnd] = useState<{ x: number; timestamp: number } | null>(null);

  const chartData: ChartRow[] = data;
  const styleByKey = resolveSeriesStyles(selectedPoints, styles);
  const colorByKey = new Map([...styleByKey].map(([key, style]) => [key, style.color]));

  // Enum points and bitfield bits are drawn by the chosen discrete renderer; the rest are analog lines.
  const discreteSeries = selectedPoints
    .map(key => describeDiscreteSeries(key, pointsById, chartData, { name: pointLabels[key] ?? key, ...styleByKey.get(key) }, functionSeries))
    .filter(Boolean);
  const discreteKeys = new Set(discreteSeries.map(series => series.key));
  const analogKeys = selectedPoints.filter(key => !discreteKeys.has(key));
  const showLanes = discreteMode === 'lanes' && discreteSeries.length > 0;
  const stepLayout = discreteMode === 'steps' && discreteSeries.length > 0 ? buildStepLayout(discreteSeries) : null;
  const showLineChart = analogKeys.length > 0 || stepLayout !== null;

  const dataStart = chartData.length ? chartData[0].timestamp : 0;
  const dataEnd = chartData.length ? chartData[chartData.length - 1].timestamp : 1;
  const domain: [number, number] = zoomRange ? [zoomRange.start, zoomRange.end] : [dataStart, dataEnd];
  const zoomedRows = zoomRange ? chartData.filter(row => row.timestamp >= zoomRange.start && row.timestamp <= zoomRange.end) : chartData;
  const displayData = stepLayout ? stepLayout.addPlotValues(zoomedRows) : zoomedRows;
  const formatTime = (timestamp: number) => formatTimestamp(timestamp, spanMs, timeZone);
  // Phones: a chart as wide as it is shaped (not as tall as the screen), short time ticks, a slim margin.
  const isPhone = useBreakpoint() === "phone";
  const chartMargin = isPhone ? PHONE_CHART_MARGIN : CHART_MARGIN;
  const formatTick = isPhone ? (timestamp: number) => formatPhoneTick(timestamp, spanMs, timeZone) : formatTime;

  // Each analog line's axis: per unit by default, so a 1-10 signal isn't flattened by a 1000-5000 one.
  const unitOf = (key: string): string | null => {
    if (parseFunctionSelectionId(key)) return functionSeries.get(key)?.unit ?? null;
    if (parseForecastSelectionId(key)) return forecastSeries.get(key)?.unit ?? null;
    return pointsById.get(parseSelectionId(key).pointId)?.point.unit ?? null;
  };
  const { theme } = useTheme();
  const { axes, axisOf } = assignAxes(
    analogKeys.map(key => ({ key, unit: unitOf(key), label: pointLabels[key] ?? key, color: colorByKey.get(key) })),
    scale,
    UNIT_AXIS_COLORS[theme],
  );
  // Each axis as wide as its numbers (and its label), so the label sits next to its ticks.
  // Memoised: a 3-day line is ~26k samples, and dragging to zoom re-renders on every mouse move.
  const axesSignature = axes.map(axis => `${axis.id}:${axis.keys.join(",")}:${axis.label !== ""}`).join("|");
  const widthOf = useMemo(
    () => new Map(axes.map(axis => [axis.id, axisWidth(valueRange(lines, axis.keys), axis.label !== "")])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [lines, axesSignature],
  );
  const sideWidth = (side: "left" | "right") =>
    axes.filter(axis => axis.side === side).reduce((total, axis) => total + (widthOf.get(axis.id) ?? 0), 0);

  // Horizontal extent of the plot area, so the lanes line up with the chart and drag maps to time.
  const plotLeft = chartMargin.left + sideWidth("left");
  const plotRight = chartMargin.right + sideWidth("right") + (stepLayout ? STATE_AXIS_WIDTH : 0);

  const getTimestampFromX = (x: number, containerWidth: number): number => {
    if (!chartData.length) return 0;
    const plotWidth = Math.max(containerWidth - plotLeft - plotRight, 1);
    const fraction = Math.max(0, Math.min((x - plotLeft) / plotWidth, 1));
    return domain[0] + fraction * (domain[1] - domain[0]);
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
      {selectedPoints.length > 0 && (
        <div className="flex items-center justify-end gap-4">
          {isFetching && <span className="text-xs text-muted-foreground">Updating...</span>}
          <SeriesStylePopover keys={selectedPoints} labels={pointLabels} resolved={styleByKey} styles={styles} onChange={onStylesChange} />
          {analogKeys.length > 1 && <AxisScaleToggle scale={scale} onChange={onScaleChange} />}
          {discreteSeries.length > 0 && <DiscreteModeToggle mode={discreteMode} onChange={onDiscreteModeChange} />}
          {zoomRange && (
            <Button variant="outline" size="sm" onClick={() => setZoomRange(null)} className="gap-2">
              <RotateCcw className="w-4 h-4" />Reset Zoom
            </Button>
          )}
        </div>
      )}
      <div
        ref={chartContainerRef}
        className="relative cursor-crosshair select-none space-y-3"
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
        {showLineChart && (
          <div className={showLanes
            ? "w-full aspect-[16/10] max-h-[55dvh] md:aspect-auto md:max-h-none md:h-[min(22rem,55dvh)]"
            : "w-full aspect-[4/3] max-h-[70dvh] md:aspect-auto md:max-h-none md:h-[min(28rem,70dvh)]"}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={displayData} margin={chartMargin}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis dataKey="timestamp" type="number" scale="time" domain={domain} allowDataOverflow tick={{ fontSize: 11 }} tickFormatter={formatTick} minTickGap={24} />
                {axes.length === 0 && <YAxis width={0} hide />}
                {axes.map(axis => (
                  <YAxis
                    key={axis.id}
                    yAxisId={axis.id}
                    orientation={axis.side}
                    width={widthOf.get(axis.id)}
                    stroke={axis.color}
                    tick={{ fontSize: isPhone ? 11 : 12, fill: axis.color }}
                    label={axis.label ? {
                      value: axis.label, angle: -90, fontSize: 11, fill: axis.color,
                      // offset 8: the rotated label's middle, half of its strip, so the outer one isn't clipped
                      position: axis.side === "left" ? "insideLeft" : "insideRight", offset: 8, style: { textAnchor: "middle" },
                    } : undefined}
                  />
                ))}
                <RechartsTooltip
                  content={<TrendTooltip lines={lines} analogKeys={analogKeys} pointLabels={pointLabels} colorByKey={colorByKey} formatTime={formatTime} stepLayout={stepLayout} />}
                />
                {scale === "per-unit" ? (
                  <Legend
                    content={(
                      <AxisGroupedLegend
                        axes={axes}
                        axisOf={axisOf}
                        onSelect={dataKey => onRevealPoint(stepLayout?.selectionKey(dataKey) ?? dataKey)}
                        styleOf={dataKey => styleByKey.get(stepLayout?.selectionKey(dataKey) ?? dataKey)}
                      />
                    )}
                  />
                ) : (
                  <Legend
                    wrapperStyle={{ paddingTop: '20px', cursor: 'pointer' }}
                    iconType="plainline"
                    formatter={(value) => <span title="Show in Trends panel">{value.includes(' - ') ? value.replace(' - ', '-') : value}</span>}
                    onClick={(entry) => { const key = stepLayout?.selectionKey(entry.dataKey) ?? entry.dataKey; if (typeof key === 'string') onRevealPoint(key); }}
                  />
                )}
                {analogKeys.map(point => {
                  // Each line draws its own samples (every reading up to 3 days, plot values beyond),
                  // breaking only at its own gap markers. Linear and unanimated: up to ~26k points a line.
                  // A PV forecast value is the mean of its 15-minute interval: drawn as a step (dashed
                  // by default), so it never blends into (or resamples) the seconds-level points next to it.
                  const isForecast = parseForecastSelectionId(point) !== null;
                  const style = styleByKey.get(point);
                  return (
                    <Line key={point} yAxisId={axisOf.get(point)} data={lines[point]} type={isForecast ? "stepAfter" : "linear"} isAnimationActive={false} dataKey={point} stroke={style.color} strokeWidth={style.width} strokeDasharray={DASH_ARRAY[style.dash]} dot={false} name={pointLabels[point] ?? point} />
                  );
                })}
                {stepLayout && renderStepSeries(stepLayout)}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        {showLanes && (
          <StateLanes
            series={discreteSeries}
            rows={chartData}
            domain={domain}
            plotLeft={plotLeft}
            plotRight={plotRight}
            formatTime={formatTime}
            showTimeAxis={!showLineChart}
            onLaneNameClick={onRevealPoint}
          />
        )}
      </div>
      {(showLineChart || showLanes) && (
        <p className="hidden items-center gap-1.5 text-xs text-muted-foreground [@media(max-width:767px)_and_(orientation:portrait)]:flex">
          <Smartphone className="h-3.5 w-3.5 rotate-90" aria-hidden="true" />
          Turn your phone sideways for a wider chart.
        </p>
      )}
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
  // Wide = 1.5x the default panel width (20rem → 30rem), for long device and point names.
  const [isSidebarWide, setIsSidebarWide] = useState(false);
  const previousSidebarStateRef = useRef<boolean | null>(null);
  const previousNotesStateRef = useRef<boolean | null>(null);
  // Below laptop width the Trends panel is a drawer over the charts, not a column beside them.
  const isLaptop = useBreakpoint() === "laptop";
  const [isTrendsDrawerOpen, setIsTrendsDrawerOpen] = useState(false);

  useEffect(() => {
    // The Notes column and the Trends panel share the laptop width; smaller layouts use drawers.
    if (!isLaptop) return;
    if (!isNotesCollapsed) {
      if (previousSidebarStateRef.current === null) previousSidebarStateRef.current = isSidebarOpen;
      setIsSidebarOpen(false);
    } else {
      if (previousSidebarStateRef.current !== null) {
        setIsSidebarOpen(previousSidebarStateRef.current);
        previousSidebarStateRef.current = null;
      }
    }
  }, [isNotesCollapsed, isLaptop]);

  const handleTrendsPanelToggle = () => {
    if (!isLaptop) {
      setIsTrendsDrawerOpen(open => !open);
    } else if (!isSidebarOpen && !isNotesCollapsed) {
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

  // A series name in a chart was clicked: make that chart's trend current (the tree edits the
  // current trend), open the Trends panel, and have the tree scroll to the point.
  const [revealRequest, setRevealRequest] = useState<RevealRequest | null>(null);
  const handleRevealPoint = (trendId: string, selectionId: string) => {
    setCurrentTrendId(trendId);
    if (!isLaptop) setIsTrendsDrawerOpen(true);
    else if (!isSidebarOpen) handleTrendsPanelToggle();
    setRevealRequest({ selectionId, requestId: Date.now() });
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
  // Off by default: the charts refresh only on Refresh, or every minute while this is on.
  const [autoRefresh, setAutoRefresh] = useState(false);
  // How far past now the PV forecast runs on a preset window (the "Forecast ahead" select).
  const [forecastAhead, setForecastAhead] = useState<ForecastAheadHours>(0);
  // A trend's axis choice is saved with the trend (localStorage, like its points).
  const scaleOf = (trendId: string | null): AxisScale => trends.find(trend => trend.id === trendId)?.scale ?? DEFAULT_AXIS_SCALE;
  const setTrendScale = (trendId: string | null, scale: AxisScale) =>
    setTrends(previous => previous.map(trend => (trend.id === trendId ? { ...trend, scale } : trend)));
  // So are its signal styles.
  const stylesOf = (trendId: string | null) => trends.find(trend => trend.id === trendId)?.styles;
  const setTrendStyles = (trendId: string | null, styles: Record<string, SeriesStyle> | undefined) =>
    setTrends(previous => previous.map(trend => (trend.id === trendId ? { ...trend, styles } : trend)));
  // A custom range is kept as UTC instants; the inputs show and take it in the display zone.
  const [customStart, setCustomStart] = useState<string>(() => new Date(Date.now() - 3_600_000).toISOString());
  const [customEnd, setCustomEnd] = useState<string>(() => new Date().toISOString());
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
  const { timeZone, display, setDisplay, siteTimeZone } = useDisplayTimeZone(selectedSite?.timezone);

  const previousSiteIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedSiteId) return;
    if (previousSiteIdRef.current && previousSiteIdRef.current !== selectedSiteId) {
      setTrends(prev => prev.map(t => ({ ...t, points: [], styles: undefined })));
      setPointLabels({});
    }
    previousSiteIdRef.current = selectedSiteId;
  }, [selectedSiteId]);

  const timeWindow: TimeWindow = timeRange === 'custom'
    ? { startTime: customStart, endTime: customEnd }
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

  // The newest device reading across the trends on screen, as each chart reports it after a fetch.
  const [latestReadingByTrend, setLatestReadingByTrend] = useState<Record<string, number | null>>({});
  const handleLatestReading = (trendId: string, timestamp: number | null) =>
    setLatestReadingByTrend(previous => (previous[trendId] === timestamp ? previous : { ...previous, [trendId]: timestamp }));
  const visibleTrendIds = [topTrendId, middleTrendId, bottomTrendId, fourthTrendId].slice(0, layoutCount).filter(Boolean);
  const latestReadings = visibleTrendIds.map(trendId => latestReadingByTrend[trendId]).filter((timestamp): timestamp is number => typeof timestamp === 'number');
  const lastDataTimeString = latestReadings.length > 0
    ? new Date(Math.max(...latestReadings)).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone })
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
  const [discreteMode, setDiscreteMode] = useState<DiscreteModeId>(DEFAULT_DISCRETE_MODE);

  useEffect(() => { if (user?.id) setDiscreteMode(loadDiscreteMode(user.id)); }, [user?.id]);

  const handleDiscreteModeChange = (mode: DiscreteModeId) => {
    setDiscreteMode(mode);
    if (user?.id) saveDiscreteMode(user.id, mode);
  };

  const updateCurrentTrendPoints = (points: string[], labels: Record<string, string>) => {
    setPointLabels(prev => ({ ...prev, ...labels }));
    setTrends(prev => prev.map(trend => trend.id === currentTrendId ? { ...trend, points, styles: pruneSeriesStyles(trend.styles, points) } : trend));
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
      setTrends(prev => prev.map(t => t.id === trendId ? { ...t, points: [], styles: undefined } : t));
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


  // The Trends panel's contents: a column beside the charts on laptops, a drawer below that.
  const trendsPanel = (
    <>
      <div className="shrink-0 border-b border-border px-4 py-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Trends Panel</h2>
        {isLaptop && <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7" aria-pressed={isSidebarWide}
                aria-label={isSidebarWide ? "Narrow the trends panel" : "Widen the trends panel"}
                onClick={() => setIsSidebarWide(wide => !wide)}>
                {isSidebarWide ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
            </TooltipTrigger>
            <TooltipContent><p>{isSidebarWide ? "Narrow panel" : "Widen panel"}</p></TooltipContent>
          </Tooltip>
        </TooltipProvider>}
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
            expandBitfields
            includeFunctions
            includeForecast
            revealRequest={revealRequest}
          />
        </section>
      </div>
    </>
  );

  return (
    // Laptops: header fixed, charts scroll in their pane. Smaller screens: the whole page scrolls,
    // so the header moves out of the way and the charts get the screen.
    <div className="min-h-full flex flex-col xl:h-full">
      <div className="border-b border-border p-4 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-foreground">Historian</h1>
            <p className="hidden text-muted-foreground mt-1 sm:block">Time-series data analysis and trending</p>
          </div>
          <div className="flex flex-wrap gap-2">
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

      <div className="flex-1 flex xl:overflow-hidden">
        {isLaptop ? (
          <>
          <div className={`border-r border-border transition-all duration-300 ease-in-out flex flex-col ${!isSidebarOpen ? 'w-0 opacity-0' : isSidebarWide ? 'w-[30rem]' : 'w-80'}`}>
            <div className={`flex-1 overflow-hidden flex flex-col ${isSidebarWide ? 'min-w-[30rem]' : 'min-w-[20rem]'}`}>
              {trendsPanel}
            </div>
          </div>

            <div className="relative border-r border-border flex flex-col justify-center">
              <Button variant="ghost" size="icon" className="h-12 w-4 rounded-none rounded-r-md border-y border-r border-border -ml-[1px] z-10 bg-background hover:bg-muted" onClick={handleTrendsPanelToggle}>
                {isSidebarOpen ? <PanelLeftClose className="h-3 w-3" /> : <PanelLeftOpen className="h-3 w-3" />}
              </Button>
            </div>
          </>
        ) : (
          <Sheet open={isTrendsDrawerOpen} onOpenChange={setIsTrendsDrawerOpen}>
            <SheetContent side="left" aria-describedby={undefined} className="flex w-full flex-col gap-0 p-0 sm:max-w-md">
              <SheetTitle className="sr-only">Trends panel</SheetTitle>
              {trendsPanel}
            </SheetContent>
          </Sheet>
        )}

        <div className="flex-1 min-w-0 flex flex-col">
          {selectedPoints.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-6">
              <div className="w-16 h-16 bg-muted/50 rounded-full flex items-center justify-center mb-4">
                <Network className="w-8 h-8 opacity-50" />
              </div>
              <h3 className="text-lg font-semibold mb-2">No Device Selected</h3>
              <p className="max-w-sm text-center">Select a data point from the Asset tree in the Trends Panel to view historical trends.</p>
              {!isLaptop && (
                <Button variant="outline" size="sm" className="mt-4 gap-2" onClick={() => setIsTrendsDrawerOpen(true)}>
                  <PanelLeftOpen className="w-4 h-4" />Open Trends Panel
                </Button>
              )}
            </div>
          ) : (
            <div className="h-full flex flex-col">
              <div className="border-b border-border px-4 py-3 md:px-6 md:py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  {!isLaptop && (
                    <Button variant="outline" size="sm" className="gap-2" onClick={() => setIsTrendsDrawerOpen(true)}>
                      <PanelLeftOpen className="w-4 h-4" />Trends Panel
                    </Button>
                  )}
                  <div className="flex items-center gap-2 min-w-0 basis-full overflow-x-auto xl:basis-auto xl:flex-1">
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
                  <div className="flex flex-wrap items-center gap-2">
                    <Select value={currentTrendId} onValueChange={setCurrentTrendId}>
                      <SelectTrigger className="hidden sm:flex sm:w-[200px]"><SelectValue placeholder="Select a trend" /></SelectTrigger>
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

              <div className="flex-1 p-2 sm:p-4 md:p-6 [@media(max-height:499px)_and_(max-width:1023px)]:p-1 xl:overflow-y-auto">
                <Card>
                  <CardHeader className="p-4 md:p-6">
                    <div className="flex items-center justify-end">
                      <div className="flex flex-col items-start gap-2 sm:items-end">
                        <div className="flex flex-wrap items-center gap-2">
                          <Label htmlFor="time-range">Time Range</Label>
                          <Select value={timeRange} onValueChange={(v) => setTimeRange(v as TimeRange | 'custom')}>
                            <SelectTrigger className="w-[160px]" id="time-range"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {PRESET_LABELS.map(([v, label]) => (
                                <SelectItem key={v} value={v}>{label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <RefreshReadingsButton siteId={selectedSiteId || null} />
                          <AutoRefreshToggle enabled={autoRefresh} onChange={setAutoRefresh} />
                        </div>
                        {timeRange === 'custom' && (
                          <div className="flex flex-wrap items-center gap-2">
                            <Input type="datetime-local" aria-label={`From (${timeZone})`} value={toZonedInput(customStart, timeZone)} onChange={e => e.target.value && setCustomStart(fromZonedInput(e.target.value, timeZone))} className="w-[180px]" />
                            <span className="text-muted-foreground text-sm">to</span>
                            <Input type="datetime-local" aria-label={`To (${timeZone})`} value={toZonedInput(customEnd, timeZone)} onChange={e => e.target.value && setCustomEnd(fromZonedInput(e.target.value, timeZone))} className="w-[180px]" />
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground flex items-center gap-1 [@media(hover:none)]:hidden">
                          <ZoomIn className="w-3 h-3" /><span>Drag to zoom</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Label htmlFor="forecast-ahead" className="text-xs text-muted-foreground">Forecast ahead</Label>
                          <Select value={String(forecastAhead)} onValueChange={value => setForecastAhead(Number(value) as ForecastAheadHours)}>
                            <SelectTrigger id="forecast-ahead" className="h-8 w-[90px] text-sm"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {FORECAST_AHEAD_HOURS.map(hours => (
                                <SelectItem key={hours} value={String(hours)}>{hours === 0 ? "None" : `+${hours} h`}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <TimeZoneToggle siteTimeZone={siteTimeZone} display={display} onDisplayChange={setDisplay} />
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent ref={cardContentRef} className="p-2 pt-0 sm:p-4 sm:pt-0 md:p-6 md:pt-0 [@media(max-height:499px)_and_(max-width:1023px)]:p-2 [@media(max-height:499px)_and_(max-width:1023px)]:pt-0">
                    <div className="space-y-6">
                      {layoutCount >= 1 && topTrendId && (
                        <div ref={topTrendRef} className="border rounded-lg p-2 sm:p-4 [@media(max-height:499px)_and_(max-width:1023px)]:p-2 bg-card space-y-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <Label>Trend-1: {trends.find(t => t.id === topTrendId)?.name || ''}</Label>
                            {layoutCount === 1 && (
                              <Select value={topTrendId} onValueChange={(v) => setTopTrendId(v)}>
                                <SelectTrigger className="w-[200px]"><SelectValue /></SelectTrigger>
                                <SelectContent>{trends.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                              </Select>
                            )}
                          </div>
                          <TrendChart selectedPoints={trends.find(t => t.id === topTrendId)?.points || []} timeWindow={timeWindow} timeZone={timeZone} autoRefresh={autoRefresh} forecastAheadHours={forecastAhead} scale={scaleOf(topTrendId)} onScaleChange={scale => setTrendScale(topTrendId, scale)} styles={stylesOf(topTrendId)} onStylesChange={styles => setTrendStyles(topTrendId, styles)} pointLabels={pointLabels} siteId={selectedSiteId || null} discreteMode={discreteMode} onDiscreteModeChange={handleDiscreteModeChange} onRevealPoint={selectionId => handleRevealPoint(topTrendId, selectionId)} onLatestReading={timestamp => handleLatestReading(topTrendId, timestamp)} />
                        </div>
                      )}
                      {layoutCount >= 2 && middleTrendId && (
                        <div ref={middleTrendRef} className="border rounded-lg p-2 sm:p-4 [@media(max-height:499px)_and_(max-width:1023px)]:p-2 bg-card space-y-2">
                          <Label>Trend-2: {trends.find(t => t.id === middleTrendId)?.name || ''}</Label>
                          <TrendChart selectedPoints={trends.find(t => t.id === middleTrendId)?.points || []} timeWindow={timeWindow} timeZone={timeZone} autoRefresh={autoRefresh} forecastAheadHours={forecastAhead} scale={scaleOf(middleTrendId)} onScaleChange={scale => setTrendScale(middleTrendId, scale)} styles={stylesOf(middleTrendId)} onStylesChange={styles => setTrendStyles(middleTrendId, styles)} pointLabels={pointLabels} siteId={selectedSiteId || null} discreteMode={discreteMode} onDiscreteModeChange={handleDiscreteModeChange} onRevealPoint={selectionId => handleRevealPoint(middleTrendId, selectionId)} onLatestReading={timestamp => handleLatestReading(middleTrendId, timestamp)} />
                        </div>
                      )}
                      {layoutCount >= 3 && bottomTrendId && (
                        <div ref={bottomTrendRef} className="border rounded-lg p-2 sm:p-4 [@media(max-height:499px)_and_(max-width:1023px)]:p-2 bg-card space-y-2">
                          <Label>Trend-3: {trends.find(t => t.id === bottomTrendId)?.name || ''}</Label>
                          <TrendChart selectedPoints={trends.find(t => t.id === bottomTrendId)?.points || []} timeWindow={timeWindow} timeZone={timeZone} autoRefresh={autoRefresh} forecastAheadHours={forecastAhead} scale={scaleOf(bottomTrendId)} onScaleChange={scale => setTrendScale(bottomTrendId, scale)} styles={stylesOf(bottomTrendId)} onStylesChange={styles => setTrendStyles(bottomTrendId, styles)} pointLabels={pointLabels} siteId={selectedSiteId || null} discreteMode={discreteMode} onDiscreteModeChange={handleDiscreteModeChange} onRevealPoint={selectionId => handleRevealPoint(bottomTrendId, selectionId)} onLatestReading={timestamp => handleLatestReading(bottomTrendId, timestamp)} />
                        </div>
                      )}
                      {layoutCount >= 4 && fourthTrendId && (
                        <div ref={fourthTrendRef} className="border rounded-lg p-2 sm:p-4 [@media(max-height:499px)_and_(max-width:1023px)]:p-2 bg-card space-y-2">
                          <Label>Trend-4: {trends.find(t => t.id === fourthTrendId)?.name || ''}</Label>
                          <TrendChart selectedPoints={trends.find(t => t.id === fourthTrendId)?.points || []} timeWindow={timeWindow} timeZone={timeZone} autoRefresh={autoRefresh} forecastAheadHours={forecastAhead} scale={scaleOf(fourthTrendId)} onScaleChange={scale => setTrendScale(fourthTrendId, scale)} styles={stylesOf(fourthTrendId)} onStylesChange={styles => setTrendStyles(fourthTrendId, styles)} pointLabels={pointLabels} siteId={selectedSiteId || null} discreteMode={discreteMode} onDiscreteModeChange={handleDiscreteModeChange} onRevealPoint={selectionId => handleRevealPoint(fourthTrendId, selectionId)} onLatestReading={timestamp => handleLatestReading(fourthTrendId, timestamp)} />
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
