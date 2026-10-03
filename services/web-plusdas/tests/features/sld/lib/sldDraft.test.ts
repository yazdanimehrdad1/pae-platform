import { describe, expect, it } from "vitest";
import type { SiteSld } from "@/api/types/sld";
import {
  addBus,
  addNode,
  autoPlace,
  connect,
  connectedTo,
  disconnect,
  draftErrors,
  idFromName,
  moveElement,
  newDraft,
  removeElement,
  rolesForType,
  setRolePoint,
  updateNode,
} from "@/features/sld/lib/sldDraft";

// grid at (0,0) feeding an MV bus on row 1 spanning columns -1..1 (cells -1, 0, 1)
function withBus(): SiteSld {
  return {
    schema_version: 1,
    nodes: [{ id: "utility", type: "grid", name: "Utility Grid", col: 0, row: 0 }],
    buses: [{ id: "mv_bus", name: "MV Bus", row: 1, col_start: -1, col_end: 1 }],
    connections: [{ from_id: "utility", to_id: "mv_bus" }],
  };
}

const nodeById = (draft: SiteSld, id: string) => draft.nodes.find((node) => node.id === id)!;

describe("newDraft", () => {
  it("starts with a utility grid, which is valid", () => {
    expect(newDraft().nodes.map((node) => node.type)).toEqual(["grid"]);
    expect(draftErrors(newDraft())).toEqual([]);
  });
});

describe("addNode with automatic placement", () => {
  it("puts it under its bus in the first free column the bus spans, and connects it", () => {
    const { draft, id } = addNode(withBus(), { type: "bess", name: "BESS 1", upstreamId: "mv_bus" });
    expect(nodeById(draft, id)).toMatchObject({ col: -1, row: 2 });
    expect(connectedTo(draft, id)).toEqual(["mv_bus"]);
  });

  it("takes the next free column under the bus", () => {
    let draft = addNode(withBus(), { type: "bess", name: "A", upstreamId: "mv_bus" }).draft;
    const second = addNode(draft, { type: "pv", name: "B", upstreamId: "mv_bus" });
    draft = second.draft;
    expect(nodeById(draft, second.id)).toMatchObject({ col: 0, row: 2 });
  });

  it("extends a full bus by one column", () => {
    let draft = withBus();
    for (const name of ["A", "B", "C"]) draft = addNode(draft, { type: "load", name, upstreamId: "mv_bus" }).draft;
    const { draft: extended, id } = addNode(draft, { type: "load", name: "D", upstreamId: "mv_bus" });
    expect(nodeById(extended, id)).toMatchObject({ col: 2, row: 2 });
    expect(extended.buses![0].col_end).toBe(2.5);
  });

  it("puts it under a node, moving right past taken cells", () => {
    let draft = addNode(newDraft(), { type: "meter", name: "Meter", upstreamId: "utility" }).draft;
    expect(nodeById(draft, "meter")).toMatchObject({ col: 0, row: 1 });
    draft = addNode(draft, { type: "breaker", name: "Breaker", upstreamId: "utility" }).draft;
    expect(nodeById(draft, "breaker")).toMatchObject({ col: 1, row: 1 });
  });

  it("uses the clicked cell instead when there is one", () => {
    const { draft, id } = addNode(withBus(), { type: "pv", name: "PV", upstreamId: "mv_bus", cell: { col: 5, row: 4 } });
    expect(nodeById(draft, id)).toMatchObject({ col: 5, row: 4 });
    expect(connectedTo(draft, id)).toEqual(["mv_bus"]);
  });

  it("without an upstream goes below everything, unconnected", () => {
    const { draft, id } = addNode(withBus(), { type: "load", name: "Island load" });
    expect(nodeById(draft, id).row).toBe(2);
    expect(connectedTo(draft, id)).toEqual([]);
  });
});

describe("ids", () => {
  it("are made from the name and kept unique", () => {
    let draft = newDraft();
    draft = addNode(draft, { type: "bess", name: "BESS #1", upstreamId: "utility" }).draft;
    expect(idFromName(draft, "BESS #1")).toBe("bess_1_2");
    expect(idFromName(draft, "!!!")).toBe("element");
  });
});

describe("addBus", () => {
  it("goes one row under the node it is fed from, centered on it", () => {
    const { draft, id } = addBus(newDraft(), { name: "MV Bus", upstreamId: "utility", span: 4 });
    expect(draft.buses!.find((bus) => bus.id === id)).toMatchObject({ row: 1, col_start: -2, col_end: 2 });
    expect(connectedTo(draft, id)).toEqual(["utility"]);
  });
});

describe("connections", () => {
  it("connect ignores self-loops and duplicates in either direction", () => {
    const draft = withBus();
    expect(connect(draft, "utility", "utility")).toBe(draft);
    expect(connect(draft, "mv_bus", "utility")).toBe(draft);
  });

  it("disconnect removes the connection in either direction", () => {
    expect(disconnect(withBus(), "mv_bus", "utility").connections).toEqual([]);
  });

  it("removing an element drops its connections", () => {
    const { draft, id } = addNode(withBus(), { type: "bess", name: "BESS", upstreamId: "mv_bus" });
    const removed = removeElement(draft, "mv_bus");
    expect(removed.buses).toEqual([]);
    expect(removed.connections).toEqual([]);
    expect(nodeById(removed, id)).toBeDefined();
  });
});

describe("moveElement", () => {
  it("moves a node to the cell, and a bus to the row centered on the column keeping its width", () => {
    const draft = moveElement(moveElement(withBus(), "utility", { col: 3, row: 0 }), "mv_bus", { col: 3, row: 2 });
    expect(nodeById(draft, "utility")).toMatchObject({ col: 3, row: 0 });
    expect(draft.buses![0]).toMatchObject({ row: 2, col_start: 2, col_end: 4 });
  });
});

describe("device links", () => {
  it("lists the roles per type as the backend allows them", () => {
    expect(rolesForType("bess")).toEqual(["soc", "power", "mode"]);
    expect(rolesForType("pv")).toEqual(["power", "irradiance"]);
    expect(rolesForType("meter")).toEqual(["vab", "vbc", "vca", "ia", "ib", "ic", "in"]);
    expect(rolesForType("breaker")).toEqual([]);
  });

  it("sets and clears one role's point", () => {
    let draft = addNode(withBus(), { type: "bess", name: "BESS", upstreamId: "mv_bus", device: { device_id: 2, points: {} } }).draft;
    draft = setRolePoint(draft, "bess", "soc", 20);
    expect(nodeById(draft, "bess").device?.points).toEqual({ soc: 20 });
    draft = setRolePoint(draft, "bess", "soc", null);
    expect(nodeById(draft, "bess").device?.points).toEqual({});
  });

  it("drops roles the new type doesn't have, and the link for a type without roles", () => {
    let draft = addNode(withBus(), {
      type: "bess",
      name: "Unit",
      upstreamId: "mv_bus",
      device: { device_id: 2, points: { soc: 20, power: 21 } },
    }).draft;
    draft = updateNode(draft, "unit", { type: "pv" });
    expect(nodeById(draft, "unit").device?.points).toEqual({ power: 21 });
    draft = updateNode(draft, "unit", { type: "breaker" });
    expect(nodeById(draft, "unit").device).toBeNull();
  });
});

describe("draftErrors", () => {
  it("reports two elements on one cell", () => {
    const draft = moveElement(addNode(withBus(), { type: "load", name: "Load", upstreamId: "mv_bus" }).draft, "load", { col: 0, row: 0 });
    expect(draftErrors(draft)).toEqual(["'Utility Grid' and 'Load' are on the same cell"]);
  });

  it("reports a bus that spans nothing", () => {
    const draft: SiteSld = { ...withBus(), buses: [{ id: "mv_bus", name: "MV Bus", row: 1, col_start: 1, col_end: 1 }] };
    expect(draftErrors(draft)).toEqual(["Bus 'MV Bus' must span at least part of a column"]);
  });

  it("reports a connection to a missing element", () => {
    const draft: SiteSld = { ...withBus(), connections: [{ from_id: "utility", to_id: "ghost" }] };
    expect(draftErrors(draft)).toEqual(["A connection points to 'ghost', which no longer exists"]);
  });

  it("reports an empty diagram", () => {
    expect(draftErrors({ schema_version: 1, nodes: [], buses: [], connections: [] })).toEqual([
      "A diagram needs at least one element",
    ]);
  });
});
