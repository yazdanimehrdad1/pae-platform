import type { SiteSld, SldBus, SldNode } from "@/api/types/sld";

// Grid cell and element sizes, in SVG user units (px at zoom 1).
export const CELL_WIDTH = 200;
export const CELL_HEIGHT = 140;
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

export interface SldGeometry {
  nodes: NodeGeometry[];
  buses: BusGeometry[];
  connections: ConnectionGeometry[];
  viewBox: Rect;
}

type Element = { kind: "node"; rect: Rect } | { kind: "bus"; rect: Rect };

const centerX = (rect: Rect) => rect.x + rect.width / 2;
const centerY = (rect: Rect) => rect.y + rect.height / 2;
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

function nodeRect(node: SldNode): Rect {
  return {
    x: node.col * CELL_WIDTH - NODE_WIDTH / 2,
    y: node.row * CELL_HEIGHT - NODE_HEIGHT / 2,
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
  };
}

function busRect(bus: SldBus): Rect {
  return {
    x: bus.col_start * CELL_WIDTH,
    y: bus.row * CELL_HEIGHT - BUS_HEIGHT / 2,
    width: (bus.col_end - bus.col_start) * CELL_WIDTH,
    height: BUS_HEIGHT,
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

/** Lay out a site's SLD in SVG units, with a viewBox that contains every element and label. */
export function computeSldGeometry(sld: SiteSld): SldGeometry {
  const nodes = sld.nodes.map((node) => ({ node, rect: nodeRect(node) }));
  const buses = (sld.buses ?? []).map((bus) => {
    const rect = busRect(bus);
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

  const boxes: Rect[] = [
    ...nodes.map(({ rect }) => rect),
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
    viewBox: { x: minX, y: minY, width: maxX - minX, height: maxY - minY },
  };
}
