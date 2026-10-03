// @vitest-environment jsdom
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SiteSld } from "@/api/types/sld";
import { computeSldGeometry } from "@/features/sld/lib/sldGeometry";
import { SiteSldDiagram } from "@/features/sld/components/SiteSldDiagram";

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

describe("SiteSldDiagram in edit mode", () => {
  const editing = () => ({ selectedId: null, selectedCell: null, onSelectElement: vi.fn(), onSelectCell: vi.fn() });

  it("reports clicks on elements, buses and empty cells", () => {
    const handlers = editing();
    const { container } = render(
      <SiteSldDiagram geometry={computeSldGeometry(sld, { editing: true })} zoom={1} editing={handlers} />,
    );
    fireEvent.click(container.querySelector('[data-node="plant"]')!);
    fireEvent.click(container.querySelector('[data-bus="mv_bus"]')!);
    fireEvent.click(container.querySelector('[data-cell="2,3"]')!);
    expect(handlers.onSelectElement.mock.calls).toEqual([["plant"], ["mv_bus"]]);
    expect(handlers.onSelectCell).toHaveBeenCalledWith({ col: 2, row: 3 });
  });

  it("offers only empty cells", () => {
    const { container } = render(
      <SiteSldDiagram geometry={computeSldGeometry(sld, { editing: true })} zoom={1} editing={editing()} />,
    );
    expect(container.querySelector('[data-cell="0,0"]')).toBeNull(); // the utility node is there
    expect(container.querySelector('[data-cell="1,0"]')).not.toBeNull();
  });
});
