import { parseForecastSelectionId } from "@/shared/lib/discretePoints";

// How each signal of a trend is drawn: colour, line style and width. A trend stores only what the
// user changed (`SeriesStyle`, every field optional); the rest comes from the defaults below.

export type LineDash = "solid" | "dashed" | "dotted";

export const LINE_DASH_LABELS: Record<LineDash, string> = {
  solid: "Solid",
  dashed: "Dashed",
  dotted: "Dotted",
};

/** The SVG stroke-dasharray of each line style. */
export const DASH_ARRAY: Record<LineDash, string | undefined> = {
  solid: undefined,
  dashed: "6 3",
  dotted: "2 3",
};

export const LINE_WIDTHS = [1, 2, 3] as const;
export type LineWidth = (typeof LINE_WIDTHS)[number];

const DEFAULT_LINE_WIDTH: LineWidth = 2;

/** What the user changed for one signal; a missing field uses the default. */
export interface SeriesStyle {
  color?: string;
  dash?: LineDash;
  width?: LineWidth;
}

export interface ResolvedStyle {
  color: string;
  dash: LineDash;
  width: LineWidth;
}

export const FALLBACK_COLORS = [
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

/** A distinct colour per point, never one of `reservedColors` (the colours the user picked). */
export function getColorsForPoints(selectedPoints: string[], reservedColors: Iterable<string> = []): string[] {
  const colors: (string | null)[] = [];
  const usedColors = new Set<string>([...reservedColors].map(color => color.toUpperCase()));
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

/** Each key's style: the user's choices, else the defaults (a PV forecast is dashed, the rest solid;
 * width 2; an automatic colour that differs from every other line's). */
export function resolveSeriesStyles(keys: string[], overrides: Record<string, SeriesStyle> = {}): Map<string, ResolvedStyle> {
  const pickedColors = keys.map(key => overrides[key]?.color).filter((color): color is string => Boolean(color));
  const autoKeys = keys.filter(key => !overrides[key]?.color);
  const autoColors = getColorsForPoints(autoKeys, pickedColors);
  const autoColorOf = new Map(autoKeys.map((key, index) => [key, autoColors[index]]));
  return new Map(keys.map(key => {
    const override = overrides[key] ?? {};
    const defaultDash: LineDash = parseForecastSelectionId(key) ? "dashed" : "solid";
    return [key, {
      color: override.color ?? autoColorOf.get(key),
      dash: override.dash ?? defaultDash,
      width: override.width ?? DEFAULT_LINE_WIDTH,
    }];
  }));
}

const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;
const HSL_COLOR = /^hsl\(\s*([\d.]+),\s*([\d.]+)%,\s*([\d.]+)%\s*\)$/;

/** A colour as `#rrggbb` (what a colour input takes): hex as is, an automatic `hsl(...)` converted. */
export function toHexColor(color: string): string {
  if (HEX_COLOR.test(color)) return color.toLowerCase();
  const match = HSL_COLOR.exec(color);
  if (!match) return "#000000";
  const [hue, saturation, lightness] = [Number(match[1]), Number(match[2]) / 100, Number(match[3]) / 100];
  const chroma = saturation * Math.min(lightness, 1 - lightness);
  const channel = (offset: number) => {
    const sector = (offset + hue / 30) % 12;
    const value = lightness - chroma * Math.max(-1, Math.min(sector - 3, 9 - sector, 1));
    return Math.round(value * 255).toString(16).padStart(2, "0");
  };
  return `#${channel(0)}${channel(8)}${channel(4)}`;
}

function isLineDash(value: unknown): value is LineDash {
  return typeof value === "string" && value in LINE_DASH_LABELS;
}

function isLineWidth(value: unknown): value is LineWidth {
  return (LINE_WIDTHS as readonly unknown[]).includes(value);
}

/** The valid part of stored styles: bad fields are dropped, and entries left empty with them.
 * Undefined when nothing valid remains. */
export function sanitizeSeriesStyles(value: unknown): Record<string, SeriesStyle> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const styles: Record<string, SeriesStyle> = {};
  for (const [key, raw] of Object.entries(value as Record<string, unknown>)) {
    if (!raw || typeof raw !== "object") continue;
    const { color, dash, width } = raw as Record<string, unknown>;
    const style: SeriesStyle = {};
    if (typeof color === "string" && HEX_COLOR.test(color)) style.color = color;
    if (isLineDash(dash)) style.dash = dash;
    if (isLineWidth(width)) style.width = width;
    if (Object.keys(style).length > 0) styles[key] = style;
  }
  return Object.keys(styles).length > 0 ? styles : undefined;
}

/** `styles` without the keys no longer in `keys`; undefined when none is left. */
export function pruneSeriesStyles(styles: Record<string, SeriesStyle> | undefined, keys: string[]): Record<string, SeriesStyle> | undefined {
  if (!styles) return undefined;
  const kept = Object.fromEntries(Object.entries(styles).filter(([key]) => keys.includes(key)));
  return Object.keys(kept).length > 0 ? kept : undefined;
}
