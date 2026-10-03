import type { SiteSld, SldBus, SldConnection, SldDeviceLink, SldNode, SldNodeType } from "@/api/types/sld";
import { INFO_ROWS } from "./sldInfoRows";

// Pure edits of a draft SLD for the editor: every function returns a new draft, never mutates.
// Grid coordinates as in the SLD format: nodes sit on integer columns, a bus spans col_start..col_end.

export interface Cell {
  col: number;
  row: number;
}

export interface NewNode {
  type: SldNodeType;
  name: string;
  voltage?: string | null;
  rating?: string | null;
  device?: SldDeviceLink | null;
  // The element or bus it is fed from; it is connected to it and placed below it.
  upstreamId?: string | null;
  // An empty cell the user clicked; overrides the automatic placement.
  cell?: Cell | null;
}

export interface NewBus {
  name: string;
  voltage?: string | null;
  upstreamId?: string | null;
  cell?: Cell | null;
  // Width in columns.
  span: number;
}

export type NodePatch = Partial<Omit<SldNode, "id">>;
export type BusPatch = Partial<Omit<SldBus, "id">>;

const DEFAULT_BUS_SPAN = 3;

/** The roles each element type's info box shows (the backend allows exactly these). */
export function rolesForType(type: SldNodeType): string[] {
  return (INFO_ROWS[type] ?? []).flatMap((row) => (row.kind === "value" ? [row.role] : []));
}

export function newDraft(): SiteSld {
  return {
    schema_version: 1,
    nodes: [{ id: "utility", type: "grid", name: "Utility Grid", col: 0, row: 0 }],
    buses: [],
    connections: [],
  };
}

const busesOf = (draft: SiteSld): SldBus[] => draft.buses ?? [];
const connectionsOf = (draft: SiteSld): SldConnection[] => draft.connections ?? [];

export function elementIds(draft: SiteSld): Set<string> {
  return new Set([...draft.nodes.map((node) => node.id), ...busesOf(draft).map((bus) => bus.id)]);
}

/** A unique id from a name: lower-case words joined by '_', with a number added if taken. */
export function idFromName(draft: SiteSld, name: string): string {
  const base =
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "element";
  const taken = elementIds(draft);
  if (!taken.has(base)) return base;
  let suffix = 2;
  while (taken.has(`${base}_${suffix}`)) suffix += 1;
  return `${base}_${suffix}`;
}

function nodeAt(draft: SiteSld, cell: Cell, exceptId?: string): SldNode | undefined {
  return draft.nodes.find((node) => node.id !== exceptId && node.col === cell.col && node.row === cell.row);
}

function firstFreeColumn(draft: SiteSld, row: number, fromCol: number): number {
  let col = fromCol;
  while (nodeAt(draft, { col, row })) col += 1;
  return col;
}

/**
 * Where a new node fed from `upstreamId` goes: under a bus, the first free column the bus spans
 * (extending the bus by one column when it is full); under a node, its column or the next free
 * one to the right. Returns the draft too, since a full bus is extended.
 */
export function autoPlace(draft: SiteSld, upstreamId: string | null | undefined): { draft: SiteSld; cell: Cell } {
  const bus = busesOf(draft).find((candidate) => candidate.id === upstreamId);
  if (bus) {
    const row = bus.row + 1;
    for (let col = Math.ceil(bus.col_start); col <= Math.floor(bus.col_end); col += 1) {
      if (!nodeAt(draft, { col, row })) return { draft, cell: { col, row } };
    }
    const col = firstFreeColumn(draft, row, Math.floor(bus.col_end) + 1);
    const extended = { ...bus, col_end: col + 0.5 };
    return {
      draft: { ...draft, buses: busesOf(draft).map((candidate) => (candidate.id === bus.id ? extended : candidate)) },
      cell: { col, row },
    };
  }
  const upstream = draft.nodes.find((node) => node.id === upstreamId);
  if (upstream) {
    const row = upstream.row + 1;
    return { draft, cell: { col: firstFreeColumn(draft, row, upstream.col), row } };
  }
  const lastRow = Math.max(0, ...draft.nodes.map((node) => node.row), ...busesOf(draft).map((candidate) => candidate.row));
  return { draft, cell: { col: firstFreeColumn(draft, lastRow + 1, 0), row: lastRow + 1 } };
}

export function connect(draft: SiteSld, fromId: string, toId: string): SiteSld {
  if (fromId === toId) return draft;
  const exists = connectionsOf(draft).some(
    (connection) =>
      (connection.from_id === fromId && connection.to_id === toId) ||
      (connection.from_id === toId && connection.to_id === fromId),
  );
  if (exists) return draft;
  return { ...draft, connections: [...connectionsOf(draft), { from_id: fromId, to_id: toId }] };
}

export function disconnect(draft: SiteSld, firstId: string, secondId: string): SiteSld {
  return {
    ...draft,
    connections: connectionsOf(draft).filter(
      (connection) =>
        !(
          (connection.from_id === firstId && connection.to_id === secondId) ||
          (connection.from_id === secondId && connection.to_id === firstId)
        ),
    ),
  };
}

/** The ids of the elements connected to `id`, in connection order. */
export function connectedTo(draft: SiteSld, id: string): string[] {
  return connectionsOf(draft).flatMap((connection) =>
    connection.from_id === id ? [connection.to_id] : connection.to_id === id ? [connection.from_id] : [],
  );
}

/** Keep only the roles the type allows; no link at all for a type without an info box. */
function linkForType(type: SldNodeType, link: SldDeviceLink | null | undefined): SldDeviceLink | null {
  if (!link) return null;
  const allowed = rolesForType(type);
  if (allowed.length === 0) return null;
  const points = Object.fromEntries(Object.entries(link.points ?? {}).filter(([role]) => allowed.includes(role)));
  return { device_id: link.device_id, points };
}

export function addNode(draft: SiteSld, input: NewNode): { draft: SiteSld; id: string } {
  const id = idFromName(draft, input.name);
  const placed = input.cell ? { draft, cell: input.cell } : autoPlace(draft, input.upstreamId);
  const node: SldNode = {
    id,
    type: input.type,
    name: input.name.trim() || id,
    voltage: input.voltage || null,
    rating: input.rating || null,
    col: placed.cell.col,
    row: placed.cell.row,
    device: linkForType(input.type, input.device),
  };
  let next: SiteSld = { ...placed.draft, nodes: [...placed.draft.nodes, node] };
  if (input.upstreamId) next = connect(next, input.upstreamId, id);
  return { draft: next, id };
}

export function addBus(draft: SiteSld, input: NewBus): { draft: SiteSld; id: string } {
  const id = idFromName(draft, input.name);
  const span = input.span > 0 ? input.span : DEFAULT_BUS_SPAN;
  let row: number;
  let center: number;
  if (input.cell) {
    row = input.cell.row;
    center = input.cell.col;
  } else {
    const upstreamBus = busesOf(draft).find((bus) => bus.id === input.upstreamId);
    const upstreamNode = draft.nodes.find((node) => node.id === input.upstreamId);
    if (upstreamNode) {
      row = upstreamNode.row + 1;
      center = upstreamNode.col;
    } else if (upstreamBus) {
      row = upstreamBus.row + 2;
      center = (upstreamBus.col_start + upstreamBus.col_end) / 2;
    } else {
      row = autoPlace(draft, null).cell.row;
      center = 0;
    }
  }
  const bus: SldBus = {
    id,
    name: input.name.trim() || id,
    voltage: input.voltage || null,
    row,
    col_start: center - span / 2,
    col_end: center + span / 2,
  };
  let next: SiteSld = { ...draft, buses: [...busesOf(draft), bus] };
  if (input.upstreamId) next = connect(next, input.upstreamId, id);
  return { draft: next, id };
}

export function updateNode(draft: SiteSld, id: string, patch: NodePatch): SiteSld {
  return {
    ...draft,
    nodes: draft.nodes.map((node) => {
      if (node.id !== id) return node;
      const updated = { ...node, ...patch };
      return { ...updated, device: linkForType(updated.type, updated.device) };
    }),
  };
}

export function updateBus(draft: SiteSld, id: string, patch: BusPatch): SiteSld {
  return { ...draft, buses: busesOf(draft).map((bus) => (bus.id === id ? { ...bus, ...patch } : bus)) };
}

/** Move a node to a cell; a bus moves to the cell's row, centered on its column, keeping its width. */
export function moveElement(draft: SiteSld, id: string, cell: Cell): SiteSld {
  if (draft.nodes.some((node) => node.id === id)) return updateNode(draft, id, { col: cell.col, row: cell.row });
  const bus = busesOf(draft).find((candidate) => candidate.id === id);
  if (!bus) return draft;
  const halfSpan = (bus.col_end - bus.col_start) / 2;
  return updateBus(draft, id, { row: cell.row, col_start: cell.col - halfSpan, col_end: cell.col + halfSpan });
}

export function removeElement(draft: SiteSld, id: string): SiteSld {
  return {
    ...draft,
    nodes: draft.nodes.filter((node) => node.id !== id),
    buses: busesOf(draft).filter((bus) => bus.id !== id),
    connections: connectionsOf(draft).filter((connection) => connection.from_id !== id && connection.to_id !== id),
  };
}

/** Set (or with null, clear) one role's point of a node's device link. */
export function setRolePoint(draft: SiteSld, nodeId: string, role: string, pointId: number | null): SiteSld {
  const node = draft.nodes.find((candidate) => candidate.id === nodeId);
  if (!node?.device) return draft;
  const points = { ...(node.device.points ?? {}) };
  if (pointId === null) delete points[role];
  else points[role] = pointId;
  return updateNode(draft, nodeId, { device: { ...node.device, points } });
}

/** The rules the backend enforces on save, checked while editing. Empty when the draft is valid. */
export function draftErrors(draft: SiteSld): string[] {
  const errors: string[] = [];
  if (draft.nodes.length === 0) errors.push("A diagram needs at least one element");

  const seen = new Set<string>();
  for (const id of [...draft.nodes.map((node) => node.id), ...busesOf(draft).map((bus) => bus.id)]) {
    if (seen.has(id)) errors.push(`The id '${id}' is used twice`);
    seen.add(id);
  }

  const cells = new Map<string, string>();
  for (const node of draft.nodes) {
    const key = `${node.col},${node.row}`;
    const other = cells.get(key);
    if (other) errors.push(`'${other}' and '${node.name}' are on the same cell`);
    else cells.set(key, node.name);
    if (node.device) {
      const allowed = rolesForType(node.type);
      if (allowed.length === 0) errors.push(`'${node.name}' (${node.type}) can't be linked to a device`);
    }
  }

  for (const bus of busesOf(draft)) {
    if (!(bus.col_end > bus.col_start)) errors.push(`Bus '${bus.name}' must span at least part of a column`);
  }

  for (const connection of connectionsOf(draft)) {
    for (const end of [connection.from_id, connection.to_id]) {
      if (!seen.has(end)) errors.push(`A connection points to '${end}', which no longer exists`);
    }
  }
  return errors;
}
