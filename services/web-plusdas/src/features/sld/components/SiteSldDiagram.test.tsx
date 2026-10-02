// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SiteSld } from "@/api/types/sld";
import { computeSldGeometry } from "../lib/sldGeometry";
import { SiteSldDiagram } from "./SiteSldDiagram";

const sld: SiteSld = {
  schema_version: 1,
  nodes: [
    { id: "utility", type: "grid", name: "Utility Grid", voltage: "34.5 kV", col: 0, row: 0 },
    { id: "plant", type: "plant_controller", name: "A very long plant controller name", rating: "3.3 MW", col: 0, row: 2 },
  ],
  buses: [{ id: "mv_bus", name: "MV Bus", voltage: "34.5 kV", row: 1, col_start: -1, col_end: 1 }],
  connections: [
    { from_id: "utility", to_id: "mv_bus" },
    { from_id: "mv_bus", to_id: "plant" },
  ],
};

describe("SiteSldDiagram", () => {
  it("draws one group per node and bus and one polyline per connection", () => {
    const { container } = render(<SiteSldDiagram geometry={computeSldGeometry(sld)} zoom={1} />);
    expect(container.querySelectorAll("[data-node]")).toHaveLength(2);
    expect(container.querySelectorAll("[data-bus]")).toHaveLength(1);
    expect(container.querySelectorAll("polyline")).toHaveLength(2);
    expect(container.textContent).toContain("MV Bus (34.5 kV)");
  });

  it("truncates long names but keeps the full name in the tooltip", () => {
    const { container } = render(<SiteSldDiagram geometry={computeSldGeometry(sld)} zoom={1} />);
    const plant = container.querySelector('[data-node="plant"]')!;
    expect(plant.querySelector("title")!.textContent).toContain("A very long plant controller name");
    expect(plant.querySelector("text")!.textContent).toMatch(/…$/);
  });

  it("sizes the svg from the viewBox times the zoom", () => {
    const geometry = computeSldGeometry(sld);
    const { container } = render(<SiteSldDiagram geometry={geometry} zoom={2} />);
    const svg = container.querySelector("svg")!;
    expect(Number(svg.getAttribute("width"))).toBe(geometry.viewBox.width * 2);
    expect(Number(svg.getAttribute("height"))).toBe(geometry.viewBox.height * 2);
  });
});
