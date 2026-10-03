import type { ComponentType } from "react";
import {
  ArrowDownUp,
  Battery,
  Cpu,
  Factory,
  Gauge,
  Home,
  MapPin,
  Power,
  Sun,
  ToggleLeft,
  ToggleRight,
  Wind,
  Zap,
  type LucideProps,
} from "lucide-react";
import type { SldNodeType, SldNodeValues } from "@/api/types/sld";
import { BUS_LABEL_FONT_SIZE, NODE_HEIGHT, NODE_WIDTH, type SldGeometry } from "../lib/sldGeometry";
import type { Cell } from "../lib/sldDraft";
import { SldInfoBox } from "./SldInfoBox";

// Record over the contract enum: a new node type in backend-ot fails the typecheck here.
const NODE_ICONS: Record<SldNodeType, ComponentType<LucideProps>> = {
  grid: Zap,
  poi: MapPin,
  meter: Gauge,
  transformer: ArrowDownUp,
  breaker: ToggleRight,
  switch: ToggleLeft,
  pv: Sun,
  inverter: Cpu,
  bess: Battery,
  generator: Power,
  wind: Wind,
  load: Home,
  plant_controller: Factory,
};

const NODE_ACCENTS: Partial<Record<SldNodeType, string>> = {
  grid: "hsl(var(--primary))",
  pv: "#facc15",
  inverter: "#facc15",
  plant_controller: "#facc15",
  bess: "hsl(var(--warning))",
  wind: "#22d3ee",
};

const ICON_SIZE = 20;
const TEXT_X = 38;
const NAME_MAX_CHARS = 18;
const DETAIL_MAX_CHARS = 20;

const truncate = (text: string, maxChars: number) =>
  text.length > maxChars ? `${text.slice(0, maxChars - 1)}…` : text;

const SELECTED_STROKE = "hsl(var(--ring))";
// Buses are thin; in edit mode a wider invisible band makes them easy to click.
const BUS_HIT_HEIGHT = 18;

// Edit mode: elements and empty cells are clickable, and the selection is highlighted.
export interface SldEditInteraction {
  selectedId: string | null;
  selectedCell: Cell | null;
  onSelectElement: (id: string) => void;
  onSelectCell: (cell: Cell) => void;
}

interface SiteSldDiagramProps {
  geometry: SldGeometry;
  zoom: number;
  // Live values by element id, for the info boxes the geometry lays out.
  valuesByNode?: Map<string, SldNodeValues>;
  editing?: SldEditInteraction;
}

export const SiteSldDiagram = ({ geometry, zoom, valuesByNode, editing }: SiteSldDiagramProps) => {
  const { viewBox } = geometry;
  const occupied = new Set(geometry.nodes.map(({ node }) => `${node.col},${node.row}`));
  const emptyCells = geometry.cells.filter((cell) => !occupied.has(`${cell.col},${cell.row}`));
  const clickable = editing ? { cursor: "pointer" } : undefined;
  return (
    <svg
      data-sld-diagram=""
      role="img"
      aria-label="Single line diagram"
      viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
      width={viewBox.width * zoom}
      height={viewBox.height * zoom}
      className="block"
      style={{ fontFamily: "inherit" }}
    >
      {editing && (
        <g data-layer="cells">
          {emptyCells.map(({ col, row, rect }) => {
            const isSelected = editing.selectedCell?.col === col && editing.selectedCell?.row === row;
            return (
              <rect
                key={`${col},${row}`}
                data-cell={`${col},${row}`}
                {...rect}
                fill={isSelected ? "hsl(var(--ring) / 0.12)" : "transparent"}
                stroke={isSelected ? SELECTED_STROKE : "hsl(var(--border))"}
                strokeDasharray={isSelected ? undefined : "4 6"}
                strokeWidth={isSelected ? 2 : 1}
                style={clickable}
                onClick={() => editing.onSelectCell({ col, row })}
              />
            );
          })}
        </g>
      )}

      <g data-layer="connections" fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth={2}>
        {geometry.connections.map((connection) => (
          <polyline
            key={connection.key}
            data-connection={connection.key}
            points={connection.points.map((point) => `${point.x},${point.y}`).join(" ")}
            strokeLinejoin="round"
          />
        ))}
      </g>

      <g data-layer="buses">
        {geometry.buses.map(({ bus, rect, label, labelAnchor }) => (
          <g
            key={bus.id}
            data-bus={bus.id}
            style={clickable}
            onClick={editing ? () => editing.onSelectElement(bus.id) : undefined}
          >
            {editing && (
              <rect
                x={rect.x}
                y={rect.y + rect.height / 2 - BUS_HIT_HEIGHT / 2}
                width={rect.width}
                height={BUS_HIT_HEIGHT}
                fill="transparent"
              />
            )}
            <rect
              {...rect}
              rx={2}
              fill="hsl(var(--primary))"
              stroke={editing?.selectedId === bus.id ? SELECTED_STROKE : undefined}
              strokeWidth={editing?.selectedId === bus.id ? 3 : undefined}
            />
            <text
              x={labelAnchor.x}
              y={labelAnchor.y}
              fontSize={BUS_LABEL_FONT_SIZE}
              fontWeight={600}
              fill="hsl(var(--foreground))"
            >
              {label}
            </text>
          </g>
        ))}
      </g>

      <g data-layer="nodes">
        {geometry.nodes.map(({ node, rect }) => {
          const Icon = NODE_ICONS[node.type];
          const accent = NODE_ACCENTS[node.type] ?? "hsl(var(--border))";
          const detail = [node.voltage, node.rating].filter(Boolean).join(" · ");
          return (
            <g
              key={node.id}
              data-node={node.id}
              transform={`translate(${rect.x} ${rect.y})`}
              style={clickable}
              onClick={editing ? () => editing.onSelectElement(node.id) : undefined}
            >
              <title>{[node.name, detail].filter(Boolean).join(" — ")}</title>
              <rect
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx={8}
                fill="hsl(var(--card))"
                stroke={editing?.selectedId === node.id ? SELECTED_STROKE : accent}
                strokeWidth={editing?.selectedId === node.id ? 4 : 2}
              />
              <Icon
                x={10}
                y={(NODE_HEIGHT - ICON_SIZE) / 2}
                width={ICON_SIZE}
                height={ICON_SIZE}
                color={NODE_ACCENTS[node.type] ?? "hsl(var(--muted-foreground))"}
              />
              <text
                x={TEXT_X}
                y={detail ? 27 : NODE_HEIGHT / 2 + 4}
                fontSize={13}
                fontWeight={600}
                fill="hsl(var(--foreground))"
              >
                {truncate(node.name, NAME_MAX_CHARS)}
              </text>
              {detail && (
                <text x={TEXT_X} y={45} fontSize={11} fill="hsl(var(--muted-foreground))">
                  {truncate(detail, DETAIL_MAX_CHARS)}
                </text>
              )}
            </g>
          );
        })}
      </g>

      <g data-layer="info-boxes">
        {geometry.infoBoxes.map((box) => (
          <SldInfoBox key={box.node.id} box={box} values={valuesByNode?.get(box.node.id)} />
        ))}
      </g>
    </svg>
  );
};
