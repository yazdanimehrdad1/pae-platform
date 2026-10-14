import { Plus, X } from "lucide-react";
import type { PointStat, ReportBlock } from "@/api/types/reports";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LIMITS, UNSET_POINT } from "../../lib/draft";
import { STAT_LABELS } from "../../lib/format";
import type { BuilderOptions } from "../../types";
import { FunctionPicker } from "./FunctionPicker";
import { PointListPicker, PointPicker } from "./PointPicker";

type Block<Kind extends ReportBlock["kind"]> = Extract<ReportBlock, { kind: Kind }>;
type KpiItem = Block<"kpi">["items"][number];
type ChartSeries = Block<"chart">["series"][number];

const ALL_STATS = Object.keys(STAT_LABELS) as PointStat[];
const CHART_DETAIL = [250, 500, 1000, 2000];

export function KpiEditor({ block, options, onChange }: { block: Block<"kpi">; options: BuilderOptions; onChange: (block: Block<"kpi">) => void }) {
  const setItem = (index: number, item: KpiItem) => onChange({ ...block, items: block.items.map((current, position) => (position === index ? item : current)) });
  const numericFunctions = options.functions.filter(candidate => (candidate.numeric_fields ?? []).length > 0);
  return (
    <div className="space-y-3">
      {block.items.map((item, index) => {
        const chosenFunction = item.source === "site_function" ? numericFunctions.find(candidate => candidate.name === item.function) : undefined;
        return (
          <div key={index} className="space-y-2 rounded-md border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={item.source}
                onValueChange={source => setItem(index, source === "point_stat"
                  ? { source: "point_stat", point_id: UNSET_POINT, stat: "max", label: item.label }
                  : { source: "site_function", function: "", field: "", device_id: null, label: item.label })}
              >
                <SelectTrigger aria-label={`Figure ${index + 1} source`} className="w-48"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="point_stat">Point statistic</SelectItem>
                  <SelectItem value="site_function">Site function value</SelectItem>
                </SelectContent>
              </Select>
              <Input
                aria-label={`Figure ${index + 1} label`} placeholder="Label (optional)" className="w-56" maxLength={100}
                value={item.label ?? ""} onChange={event => setItem(index, { ...item, label: event.target.value || null })}
              />
              <Button
                type="button" size="icon" variant="ghost" className="ml-auto h-8 w-8" aria-label={`Remove figure ${index + 1}`}
                onClick={() => onChange({ ...block, items: block.items.filter((_, position) => position !== index) })}
              >
                <X aria-hidden className="h-4 w-4" />
              </Button>
            </div>
            {item.source === "point_stat" ? (
              <div className="flex flex-wrap gap-2">
                <div className="min-w-64 flex-1">
                  <PointPicker options={options.points} pointId={item.point_id} ariaLabel={`Figure ${index + 1} point`} onChange={pointId => setItem(index, { ...item, point_id: pointId })} />
                </div>
                <Select value={item.stat} onValueChange={stat => setItem(index, { ...item, stat: stat as PointStat })}>
                  <SelectTrigger aria-label={`Figure ${index + 1} statistic`} className="w-36"><SelectValue /></SelectTrigger>
                  <SelectContent>{ALL_STATS.map(stat => <SelectItem key={stat} value={stat}>{STAT_LABELS[stat]}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                <FunctionPicker
                  functions={numericFunctions} devices={options.devices} name={item.function} deviceId={item.device_id}
                  ariaLabel={`Figure ${index + 1} function`}
                  onChange={(name, deviceId) => setItem(index, { ...item, function: name, device_id: deviceId, field: "" })}
                />
                {chosenFunction && (
                  <Select value={item.field || undefined} onValueChange={field => setItem(index, { ...item, field })}>
                    <SelectTrigger aria-label={`Figure ${index + 1} value`} className="w-48"><SelectValue placeholder="Choose a value" /></SelectTrigger>
                    <SelectContent>{(chosenFunction.numeric_fields ?? []).map(field => <SelectItem key={field} value={field}>{field}</SelectItem>)}</SelectContent>
                  </Select>
                )}
              </div>
            )}
          </div>
        );
      })}
      <Button
        type="button" size="sm" variant="outline" className="gap-1.5" disabled={block.items.length >= LIMITS.kpiItems}
        onClick={() => onChange({ ...block, items: [...block.items, { source: "point_stat", point_id: UNSET_POINT, stat: "max" }] })}
      >
        <Plus aria-hidden className="h-3.5 w-3.5" />Add figure
      </Button>
    </div>
  );
}

export function ChartEditor({ block, options, onChange }: { block: Block<"chart">; options: BuilderOptions; onChange: (block: Block<"chart">) => void }) {
  const setSeries = (index: number, series: ChartSeries) => onChange({ ...block, series: block.series.map((current, position) => (position === index ? series : current)) });
  const seriesFunctions = options.functions.filter(candidate => candidate.output === "series");
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <div className="space-y-1">
          <Label htmlFor={`${block.id}-style`}>Style</Label>
          <Select value={block.style ?? "line"} onValueChange={style => onChange({ ...block, style: style as Block<"chart">["style"] })}>
            <SelectTrigger id={`${block.id}-style`} className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="line">Line</SelectItem>
              <SelectItem value="step">Steps</SelectItem>
              <SelectItem value="bar">Bars</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${block.id}-detail`}>Detail</Label>
          <Select value={String(block.max_points ?? 500)} onValueChange={detail => onChange({ ...block, max_points: Number(detail) })}>
            <SelectTrigger id={`${block.id}-detail`} className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>{CHART_DETAIL.map(detail => <SelectItem key={detail} value={String(detail)}>{detail} points per series</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>
      {block.series.map((series, index) => (
        <div key={index} className="flex flex-wrap items-center gap-2">
          <Select
            value={series.source}
            onValueChange={source => setSeries(index, source === "point"
              ? { source: "point", point_id: UNSET_POINT }
              : { source: "site_function", function: "", device_id: null })}
          >
            <SelectTrigger aria-label={`Series ${index + 1} source`} className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="point">Point</SelectItem>
              <SelectItem value="site_function" disabled={seriesFunctions.length === 0}>Site function</SelectItem>
            </SelectContent>
          </Select>
          <div className="min-w-64 flex-1">
            {series.source === "point" ? (
              <PointPicker options={options.points} pointId={series.point_id} ariaLabel={`Series ${index + 1} point`} onChange={pointId => setSeries(index, { ...series, point_id: pointId })} />
            ) : (
              <FunctionPicker
                functions={seriesFunctions} devices={options.devices} name={series.function} deviceId={series.device_id}
                ariaLabel={`Series ${index + 1} function`}
                onChange={(name, deviceId) => setSeries(index, { ...series, function: name, device_id: deviceId })}
              />
            )}
          </div>
          <Button
            type="button" size="icon" variant="ghost" className="h-8 w-8" aria-label={`Remove series ${index + 1}`}
            onClick={() => onChange({ ...block, series: block.series.filter((_, position) => position !== index) })}
          >
            <X aria-hidden className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button
        type="button" size="sm" variant="outline" className="gap-1.5" disabled={block.series.length >= LIMITS.chartSeries}
        onClick={() => onChange({ ...block, series: [...block.series, { source: "point", point_id: UNSET_POINT }] })}
      >
        <Plus aria-hidden className="h-3.5 w-3.5" />Add series
      </Button>
    </div>
  );
}

export function PointStatsTableEditor({ block, options, onChange }: {
  block: Block<"point_stats_table">;
  options: BuilderOptions;
  onChange: (block: Block<"point_stats_table">) => void;
}) {
  const stats = block.stats ?? [];
  const toggleStat = (stat: PointStat, checked: boolean) =>
    onChange({ ...block, stats: checked ? ALL_STATS.filter(candidate => candidate === stat || stats.includes(candidate)) : stats.filter(candidate => candidate !== stat) });
  return (
    <div className="space-y-3">
      <PointListPicker options={options.points} pointIds={block.point_ids} max={LIMITS.tablePoints} label="Point" onChange={pointIds => onChange({ ...block, point_ids: pointIds })} />
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Statistics</legend>
        <div className="flex flex-wrap gap-4">
          {ALL_STATS.map(stat => (
            <label key={stat} className="flex items-center gap-2 text-sm">
              <Checkbox checked={stats.includes(stat)} onCheckedChange={checked => toggleStat(stat, checked === true)} />
              {STAT_LABELS[stat]}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="space-y-1">
        <Label htmlFor={`${block.id}-bucket`}>Rows</Label>
        <Select value={block.bucket ?? "none"} onValueChange={bucket => onChange({ ...block, bucket: bucket as Block<"point_stats_table">["bucket"] })}>
          <SelectTrigger id={`${block.id}-bucket`} className="w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="none">One per point (whole period)</SelectItem>
            <SelectItem value="hour">Per point and hour</SelectItem>
            <SelectItem value="day">Per point and day</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

export function AlarmEventsTableEditor({ block, options, onChange }: {
  block: Block<"alarm_events_table">;
  options: BuilderOptions;
  onChange: (block: Block<"alarm_events_table">) => void;
}) {
  const deviceIds = block.device_ids ?? [];
  const toggleDevice = (deviceId: number, checked: boolean) =>
    onChange({ ...block, device_ids: checked ? [...deviceIds, deviceId] : deviceIds.filter(candidate => candidate !== deviceId) });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <div className="space-y-1">
          <Label htmlFor={`${block.id}-severity`}>Severity</Label>
          <Select value={block.severity ?? "all"} onValueChange={severity => onChange({ ...block, severity: severity === "all" ? null : severity as "fault" | "warning" })}>
            <SelectTrigger id={`${block.id}-severity`} className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Faults and warnings</SelectItem>
              <SelectItem value="fault">Faults only</SelectItem>
              <SelectItem value="warning">Warnings only</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${block.id}-limit`}>Rows at most</Label>
          <Input
            id={`${block.id}-limit`} type="number" min={1} max={LIMITS.alarmRows} className="w-28" value={block.limit ?? 200}
            onChange={event => onChange({ ...block, limit: Math.min(LIMITS.alarmRows, Math.max(1, Number(event.target.value) || 1)) })}
          />
        </div>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Devices <span className="font-normal text-muted-foreground">(none ticked: every device, and site-level alarms)</span></legend>
        <div className="flex flex-wrap gap-4">
          {options.devices.map(device => (
            <label key={device.deviceId} className="flex items-center gap-2 text-sm">
              <Checkbox checked={deviceIds.includes(device.deviceId)} onCheckedChange={checked => toggleDevice(device.deviceId, checked === true)} />
              {device.deviceName}
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
