import { Palette, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  DASH_ARRAY, FALLBACK_COLORS, LINE_DASH_LABELS, LINE_WIDTHS, toHexColor,
  type LineDash, type LineWidth, type ResolvedStyle, type SeriesStyle,
} from "../lib/seriesStyles";

interface SeriesStylePopoverProps {
  /** The trend's selection ids, in chart order. */
  keys: string[];
  labels: Record<string, string>;
  /** Each key's style as drawn (the user's choices over the defaults). */
  resolved: Map<string, ResolvedStyle>;
  /** Only what the user changed; saved on the trend. */
  styles: Record<string, SeriesStyle> | undefined;
  onChange: (styles: Record<string, SeriesStyle> | undefined) => void;
}

function LineSample({ style }: { style: Pick<ResolvedStyle, "dash" | "width"> & { color?: string } }) {
  return (
    <svg width="20" height="8" aria-hidden className="shrink-0">
      <line x1="0" y1="4" x2="20" y2="4" stroke={style.color ?? "currentColor"} strokeWidth={style.width} strokeDasharray={DASH_ARRAY[style.dash]} />
    </svg>
  );
}

/** Per trend: each signal's colour, line style and width. A reset drops the user's choice, so the
 * line goes back to its default look. */
export function SeriesStylePopover({ keys, labels, resolved, styles, onChange }: SeriesStylePopoverProps) {
  const update = (key: string, change: SeriesStyle) => onChange({ ...styles, [key]: { ...styles?.[key], ...change } });
  const reset = (key: string) => {
    const rest = Object.fromEntries(Object.entries(styles ?? {}).filter(([styledKey]) => styledKey !== key));
    onChange(Object.keys(rest).length > 0 ? rest : undefined);
  };
  const hasChanges = keys.some(key => styles?.[key]);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-7 gap-1.5 px-2 text-xs">
          <Palette className="h-3.5 w-3.5" />Styles
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[34rem] max-w-[calc(100vw-2rem)] space-y-3 p-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Signal styles</span>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" disabled={!hasChanges} onClick={() => onChange(undefined)}>
            Reset all
          </Button>
        </div>
        <div className="max-h-80 space-y-3 overflow-y-auto">
          {keys.map(key => {
            const style = resolved.get(key);
            if (!style) return null;
            const label = labels[key] ?? key;
            return (
              <div key={key} className="space-y-1.5 border-t border-border pt-2 first:border-t-0 first:pt-0">
                <div className="flex items-center gap-2">
                  <LineSample style={style} />
                  <span className="flex-1 truncate text-xs font-medium" title={label}>{label}</span>
                  <Button variant="ghost" size="icon" className="h-6 w-6" aria-label={`Reset ${label}`} disabled={!styles?.[key]} onClick={() => reset(key)}>
                    <RotateCcw className="h-3 w-3" />
                  </Button>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  <div className="flex items-center gap-1">
                    <input
                      type="color"
                      aria-label={`Colour of ${label}`}
                      value={toHexColor(style.color)}
                      onChange={event => update(key, { color: event.target.value })}
                      className="h-6 w-7 cursor-pointer rounded border border-border bg-transparent p-0"
                    />
                    {FALLBACK_COLORS.map(color => (
                      <button
                        key={color}
                        type="button"
                        aria-label={`${label}: ${color}`}
                        onClick={() => update(key, { color })}
                        className={`h-4 w-4 rounded-sm border ${toHexColor(style.color) === color.toLowerCase() ? "border-foreground" : "border-transparent"}`}
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                  <ToggleGroup
                    type="single"
                    size="sm"
                    variant="outline"
                    value={style.dash}
                    onValueChange={value => { if (value) update(key, { dash: value as LineDash }); }}
                    aria-label={`Line style of ${label}`}
                  >
                    {(Object.keys(LINE_DASH_LABELS) as LineDash[]).map(dash => (
                      <ToggleGroupItem key={dash} value={dash} aria-label={LINE_DASH_LABELS[dash]} title={LINE_DASH_LABELS[dash]} className="h-7 px-1.5">
                        <LineSample style={{ dash, width: 2 }} />
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                  <ToggleGroup
                    type="single"
                    size="sm"
                    variant="outline"
                    value={String(style.width)}
                    onValueChange={value => { if (value) update(key, { width: Number(value) as LineWidth }); }}
                    aria-label={`Line width of ${label}`}
                  >
                    {LINE_WIDTHS.map(width => (
                      <ToggleGroupItem key={width} value={String(width)} aria-label={`${width} px`} title={`${width} px`} className="h-7 px-1.5">
                        <LineSample style={{ dash: "solid", width }} />
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                </div>
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
