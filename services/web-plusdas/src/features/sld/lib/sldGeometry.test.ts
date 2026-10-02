import { describe, expect, it } from "vitest";
import type { SiteSld } from "@/api/types/sld";
import {
  BUS_HEIGHT,
  CELL_HEIGHT,
  CELL_WIDTH,
  NODE_HEIGHT,
  INFO_BOX_WIDTH,
  NODE_WIDTH,
  computeSldGeometry,
  type Rect,
} from "./sldGeometry";

const contains = (outer: Rect, inner: Rect) =>
  inner.x >= outer.x &&
  inner.y >= outer.y &&
  inner.x + inner.width <= outer.x + outer.width &&
  inner.y + inner.height <= outer.y + outer.height;

const sld: SiteSld = {
  schema_version: 1,
  nodes: [
    { id: "utility", type: "grid", name: "Utility", col: 1, row: 0 },
    { id: "pv_far_left", type: "pv", name: "PV West", col: -3, row: 2 },
    { id: "bess", type: "bess", name: "BESS", col: 2, row: 2 },
    { id: "outside_span", type: "load", name: "Load", col: 6, row: 2 },
  ],
  buses: [{ id: "mv_bus", name: "MV Bus", voltage: "34.5 kV", row: 1, col_start: -3, col_end: 3 }],
  connections: [
    { from_id: "utility", to_id: "mv_bus" },
    { from_id: "mv_bus", to_id: "pv_far_left" },
    { from_id: "mv_bus", to_id: "bess" },
    { from_id: "mv_bus", to_id: "outside_span" },
  ],
};

describe("computeSldGeometry", () => {
  const geometry = computeSldGeometry(sld);

  it("fits every node, bus and bus label inside the viewBox, including row 0 and negative cols", () => {
    for (const { rect } of geometry.nodes) expect(contains(geometry.viewBox, rect)).toBe(true);
    for (const { rect, labelAnchor } of geometry.buses) {
      expect(contains(geometry.viewBox, rect)).toBe(true);
      expect(labelAnchor.y - 12).toBeGreaterThanOrEqual(geometry.viewBox.y);
    }
    for (const { points } of geometry.connections) {
      for (const point of points) {
        expect(point.x).toBeGreaterThanOrEqual(geometry.viewBox.x);
        expect(point.y).toBeGreaterThanOrEqual(geometry.viewBox.y);
      }
    }
  });

  it("joins a node above a bus from its bottom edge straight down to the bus top", () => {
    const route = geometry.connections.find((connection) => connection.key === "utility->mv_bus")!.points;
    expect(route).toEqual([
      { x: CELL_WIDTH, y: NODE_HEIGHT / 2 },
      { x: CELL_WIDTH, y: CELL_HEIGHT - BUS_HEIGHT / 2 },
    ]);
  });

  it("joins a bus to a node below it from the bus bottom to the node's top edge", () => {
    const route = geometry.connections.find((connection) => connection.key === "mv_bus->bess")!.points;
    expect(route).toEqual([
      { x: 2 * CELL_WIDTH, y: CELL_HEIGHT + BUS_HEIGHT / 2 },
      { x: 2 * CELL_WIDTH, y: 2 * CELL_HEIGHT - NODE_HEIGHT / 2 },
    ]);
  });

  it("clamps the bus end of a line onto the bus span and elbows to a node beyond it", () => {
    const route = geometry.connections.find((connection) => connection.key === "mv_bus->outside_span")!.points;
    const busRight = 3 * CELL_WIDTH;
    expect(route[0].x).toBe(busRight);
    expect(route.at(-1)!.x).toBe(6 * CELL_WIDTH);
    expect(route).toHaveLength(4);
  });

  it("skips a connection to an unknown element instead of drawing to the origin", () => {
    const broken = { ...sld, connections: [{ from_id: "utility", to_id: "ghost" }] };
    expect(computeSldGeometry(broken).connections).toEqual([]);
  });

  it("joins two nodes on one row edge to edge", () => {
    const row: SiteSld = {
      schema_version: 1,
      nodes: [
        { id: "a", type: "breaker", name: "A", col: 0, row: 0 },
        { id: "b", type: "breaker", name: "B", col: 1, row: 0 },
      ],
      buses: [],
      connections: [{ from_id: "b", to_id: "a" }],
    };
    const [{ points }] = computeSldGeometry(row).connections;
    expect(points).toEqual([
      { x: 85, y: 0 },
      { x: CELL_WIDTH - 85, y: 0 },
    ]);
  });
});

describe("computeSldGeometry with info boxes", () => {
  const linked: SiteSld = {
    schema_version: 1,
    nodes: [
      { id: "pv", type: "pv", name: "PV", col: 0, row: 4, device: { device_id: 1, points: {} } },
      { id: "bess", type: "bess", name: "BESS", col: 1, row: 4, device: { device_id: 2, points: {} } },
      { id: "meter", type: "meter", name: "Meter", col: 2, row: 1, device: { device_id: 3, points: {} } },
      { id: "breaker", type: "breaker", name: "Breaker", col: 2, row: 2 },
      { id: "unlinked_bess", type: "bess", name: "Spare", col: 3, row: 4 },
    ],
    buses: [],
    connections: [],
  };
  const geometry = computeSldGeometry(linked, { showInfoBoxes: true });

  it("puts a box right of each linked meter/bess/pv node only", () => {
    expect(geometry.infoBoxes.map((box) => box.node.id)).toEqual(["pv", "bess", "meter"]);
    const pv = geometry.nodes.find((entry) => entry.node.id === "pv")!;
    const pvBox = geometry.infoBoxes.find((box) => box.node.id === "pv")!;
    expect(pvBox.rect.x).toBeGreaterThan(pv.rect.x + NODE_WIDTH);
    expect(pvBox.rect.width).toBe(INFO_BOX_WIDTH);
  });

  it("keeps every box inside the viewBox", () => {
    for (const { rect } of geometry.infoBoxes) expect(contains(geometry.viewBox, rect)).toBe(true);
  });

  it("never lets a box overlap another node, even the 7-row meter above a breaker", () => {
    const overlaps = (a: Rect, b: Rect) =>
      a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
    for (const box of geometry.infoBoxes) {
      for (const { node, rect } of geometry.nodes) {
        if (node.id !== box.node.id) expect(overlaps(box.rect, rect), `${box.node.id} vs ${node.id}`).toBe(false);
      }
    }
  });

  it("lays out compactly with no boxes by default", () => {
    expect(computeSldGeometry(linked).infoBoxes).toEqual([]);
    expect(computeSldGeometry(linked).viewBox.width).toBeLessThan(geometry.viewBox.width);
  });
});
