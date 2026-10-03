import type { SiteSld, SldBus, SldNode } from "@/api/types/sld";
import { INFO_ROWS } from "./sldInfoRows";

// Grid cell and element sizes, in SVG user units (px at zoom 1).
export const CELL_WIDTH = 200;
export const CELL_HEIGHT = 140;
// With info boxes shown, cells grow so a box fits right of its node without touching a neighbour.
export const INFO_CELL_WIDTH = 380;
export const INFO_CELL_HEIGHT = 170;
export const INFO_BOX_WIDTH = 150;
export const INFO_BOX_GAP = 8;
export const INFO_ROW_HEIGHT = 18;
export const INFO_BOX_PADDING = 6;
export const NODE_WIDTH = 170;
export const NODE_HEIGHT = 64;
export const BUS_HEIGHT = 8;
export const MARGIN = 40;
// Bus labels sit above the bus's left end; text width is estimated, not measured.
export const BUS_LABEL_FONT_SIZE = 12;
const BUS_LABEL_GAP = 6;
const LABEL_CHAR_WIDTH = 7.5;

// Finds the rendered diagram svg (not the icon svgs nested in it), e.g. to zoom around the cursor.
export const SLD_SVG_SELECTOR = "svg[data-sld-diagram]";

export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface NodeGeometry {
  node: SldNode;
  rect: Rect;
}

export interface BusGeometry {
  bus: SldBus;
  rect: Rect;
  label: string;
  labelAnchor: Point;
}

export interface ConnectionGeometry {
  key: string;
  points: Point[];
}

export interface InfoBoxGeometry {
  node: SldNode;
  rect: Rect;
}

// One grid cell in edit mode, clickable to place an element there.
export interface CellGeometry {
  col: number;
  row: number;
  rect: Rect;
}

export interface SldGeometry {
  nodes: NodeGeometry[];
  buses: BusGeometry[];
  connections: ConnectionGeometry[];
  infoBoxes: InfoBoxGeometry[];
  // Edit mode only: every cell of the diagram's extent plus one cell around it.
  cells: CellGeometry[];
  viewBox: Rect;
}

export interface SldLayoutOptions {
  // Draw an info box beside every element linked to a device (meter, bess, pv).
  showInfoBoxes?: boolean;
  // Lay out the clickable cell grid, one cell beyond the diagram on every side.
  editing?: boolean;
}

interface Cell {
  width: number;
  height: number;
}

type Element = { kind: "node"; rect: Rect } | { kind: "bus"; rect: Rect };

const centerX = (rect: Rect) => rect.x + rect.width / 2;
const centerY = (rect: Rect) => rect.y + rect.height / 2;
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

function nodeRect(node: SldNode, cell: Cell): Rect {
  return {
    x: node.col * cell.width - NODE_WIDTH / 2,
    y: node.row * cell.height - NODE_HEIGHT / 2,
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
  };
}

function busRect(bus: SldBus, cell: Cell): Rect {
  return {
    x: bus.col_start * cell.width,
    y: bus.row * cell.height - BUS_HEIGHT / 2,
    width: (bus.col_end - bus.col_start) * cell.width,
    height: BUS_HEIGHT,
  };
}

/** The info box right of a linked node, top-aligned with it; null if the node gets none. */
export function infoBoxRect(node: SldNode, nodeBox: Rect): Rect | null {
  const rows = INFO_ROWS[node.type];
  if (!node.device || !rows) return null;
  return {
    x: nodeBox.x + nodeBox.width + INFO_BOX_GAP,
    y: nodeBox.y,
    width: INFO_BOX_WIDTH,
    height: rows.length * INFO_ROW_HEIGHT + 2 * INFO_BOX_PADDING,
  };
}

export function busLabel(bus: SldBus): string {
  return bus.voltage ? `${bus.name} (${bus.voltage})` : bus.name;
}

// The x where a line meets an element: a node's center, or the given x clamped onto a bus.
function attachX(element: Element, towardX: number): number {
  if (element.kind === "node") return centerX(element.rect);
  return clamp(towardX, element.rect.x, element.rect.x + element.rect.width);
}

/**
 * Orthogonal route between two elements. Elements on different rows are joined from the
 * upper one's bottom edge to the lower one's top edge (straight down, or down / across / down);
 * elements on one row are joined edge to edge horizontally.
 */
export function routeConnection(from: Element, to: Element): Point[] {
  if (Math.abs(centerY(from.rect) - centerY(to.rect)) < 1e-6) {
    const [left, right] = centerX(from.rect) <= centerX(to.rect) ? [from, to] : [to, from];
    const y = centerY(left.rect);
    return [
      { x: left.rect.x + left.rect.width, y },
      { x: right.rect.x, y },
    ];
  }

  const [upper, lower] = centerY(from.rect) < centerY(to.rect) ? [from, to] : [to, from];
  let startX: number;
  let endX: number;
  if (upper.kind === "node") {
    startX = centerX(upper.rect);
    endX = attachX(lower, startX);
  } else {
    endX = attachX(lower, centerX(upper.rect));
    startX = attachX(upper, endX);
    if (lower.kind === "bus") endX = attachX(lower, startX);
  }

  const startY = upper.rect.y + upper.rect.height;
  const endY = lower.rect.y;
  if (Math.abs(startX - endX) < 1e-6) {
    return [
      { x: startX, y: startY },
      { x: endX, y: endY },
    ];
  }
  const midY = (startY + endY) / 2;
  return [
    { x: startX, y: startY },
    { x: startX, y: midY },
    { x: endX, y: midY },
    { x: endX, y: endY },
  ];
}

/** Every integer cell from the diagram's extent, grown by one cell on each side. */
function gridCells(sld: SiteSld, cell: Cell): CellGeometry[] {
  const cols = [
    ...sld.nodes.map((node) => node.col),
    ...(sld.buses ?? []).flatMap((bus) => [bus.col_start, bus.col_end]),
  ];
  const rows = [...sld.nodes.map((node) => node.row), ...(sld.buses ?? []).map((bus) => bus.row)];
  const minCol = Math.floor(Math.min(...cols)) - 1;
  const maxCol = Math.ceil(Math.max(...cols)) + 1;
  const minRow = Math.floor(Math.min(...rows)) - 1;
  const maxRow = Math.ceil(Math.max(...rows)) + 1;
  const cells: CellGeometry[] = [];
  for (let row = minRow; row <= maxRow; row += 1) {
    for (let col = minCol; col <= maxCol; col += 1) {
      cells.push({
        col,
        row,
        rect: { x: (col - 0.5) * cell.width, y: (row - 0.5) * cell.height, width: cell.width, height: cell.height },
      });
    }
  }
  return cells;
}

/** Lay out a site's SLD in SVG units, with a viewBox that contains every element, label and info box. */
export function computeSldGeometry(sld: SiteSld, options: SldLayoutOptions = {}): SldGeometry {
  const cell: Cell = options.showInfoBoxes
    ? { width: INFO_CELL_WIDTH, height: INFO_CELL_HEIGHT }
    : { width: CELL_WIDTH, height: CELL_HEIGHT };
  const nodes = sld.nodes.map((node) => ({ node, rect: nodeRect(node, cell) }));
  const infoBoxes = options.showInfoBoxes
    ? nodes.flatMap(({ node, rect }) => {
        const box = infoBoxRect(node, rect);
        return box ? [{ node, rect: box }] : [];
      })
    : [];
  const buses = (sld.buses ?? []).map((bus) => {
    const rect = busRect(bus, cell);
    return {
      bus,
      rect,
      label: busLabel(bus),
      labelAnchor: { x: rect.x, y: rect.y - BUS_LABEL_GAP },
    };
  });

  const elements = new Map<string, Element>();
  nodes.forEach(({ node, rect }) => elements.set(node.id, { kind: "node", rect }));
  buses.forEach(({ bus, rect }) => elements.set(bus.id, { kind: "bus", rect }));

  // The backend validates that both ends exist; skip defensively rather than draw to (0, 0).
  const connections = (sld.connections ?? []).flatMap((connection) => {
    const from = elements.get(connection.from_id);
    const to = elements.get(connection.to_id);
    if (!from || !to) return [];
    return [{ key: `${connection.from_id}->${connection.to_id}`, points: routeConnection(from, to) }];
  });

  const cells = options.editing ? gridCells(sld, cell) : [];

  const boxes: Rect[] = [
    ...nodes.map(({ rect }) => rect),
    ...infoBoxes.map(({ rect }) => rect),
    ...cells.map(({ rect }) => rect),
    ...buses.map(({ rect }) => rect),
    ...buses.map(({ label, labelAnchor }) => ({
      x: labelAnchor.x,
      y: labelAnchor.y - BUS_LABEL_FONT_SIZE,
      width: label.length * LABEL_CHAR_WIDTH,
      height: BUS_LABEL_FONT_SIZE,
    })),
  ];
  const minX = Math.min(...boxes.map((box) => box.x)) - MARGIN;
  const minY = Math.min(...boxes.map((box) => box.y)) - MARGIN;
  const maxX = Math.max(...boxes.map((box) => box.x + box.width)) + MARGIN;
  const maxY = Math.max(...boxes.map((box) => box.y + box.height)) + MARGIN;

  return {
    nodes,
    buses,
    connections,
    infoBoxes,
    cells,
    viewBox: { x: minX, y: minY, width: maxX - minX, height: maxY - minY },
  };
}
