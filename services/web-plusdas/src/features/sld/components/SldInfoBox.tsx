import type { SldNodeValues } from "@/api/types/sld";
import type { InfoBoxGeometry } from "../lib/sldGeometry";
import { INFO_BOX_PADDING, INFO_ROW_HEIGHT } from "../lib/sldGeometry";
import { INFO_ROWS, NOT_AVAILABLE, formatRowValue, healthState, type HealthState } from "../lib/sldInfoRows";

const LABEL_X = 8;
const VALUE_X_FROM_RIGHT = 8;
const FONT_SIZE = 11;

const HEALTH_TEXT: Record<HealthState, string> = {
  healthy: "Healthy",
  unhealthy: "Unhealthy",
  unknown: NOT_AVAILABLE,
};

const HEALTH_COLOR: Record<HealthState, string> = {
  healthy: "hsl(var(--success))",
  unhealthy: "hsl(var(--destructive))",
  unknown: "hsl(var(--muted-foreground))",
};

interface SldInfoBoxProps {
  box: InfoBoxGeometry;
  // The element's live values; undefined while loading or when the device has none.
  values: SldNodeValues | undefined;
}

/** The value box beside a meter, BESS or PV element: one row per value, NA when not available. */
export const SldInfoBox = ({ box, values }: SldInfoBoxProps) => {
  const rows = INFO_ROWS[box.node.type] ?? [];
  const { rect } = box;
  const valueX = rect.width - VALUE_X_FROM_RIGHT;
  return (
    <g data-info-box={box.node.id} transform={`translate(${rect.x} ${rect.y})`}>
      <rect
        width={rect.width}
        height={rect.height}
        rx={6}
        fill="hsl(var(--muted))"
        stroke="hsl(var(--border))"
        strokeWidth={1}
      />
      {rows.map((row, index) => {
        const y = INFO_BOX_PADDING + index * INFO_ROW_HEIGHT + INFO_ROW_HEIGHT * 0.7;
        let text: string;
        let color = "hsl(var(--foreground))";
        let tooltip: string | undefined;
        if (row.kind === "health") {
          const state = healthState(values);
          text = HEALTH_TEXT[state];
          color = HEALTH_COLOR[state];
          tooltip = values?.health?.reason ?? undefined;
        } else {
          text = formatRowValue(values?.values[row.role], row.unit);
          if (text === NOT_AVAILABLE) color = "hsl(var(--muted-foreground))";
        }
        return (
          <g key={row.label} data-row={row.label}>
            {tooltip && <title>{tooltip}</title>}
            <text x={LABEL_X} y={y} fontSize={FONT_SIZE} fill="hsl(var(--muted-foreground))">
              {row.label}
            </text>
            <text
              x={valueX}
              y={y}
              fontSize={FONT_SIZE}
              fontWeight={600}
              textAnchor="end"
              fill={color}
              data-value=""
            >
              {text}
            </text>
          </g>
        );
      })}
    </g>
  );
};
