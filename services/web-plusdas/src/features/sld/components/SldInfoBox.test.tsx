// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SiteSld, SldNodeValues } from "@/api/types/sld";
import { computeSldGeometry } from "../lib/sldGeometry";
import { SiteSldDiagram } from "./SiteSldDiagram";

const sld: SiteSld = {
  schema_version: 1,
  nodes: [
    { id: "bess", type: "bess", name: "BESS", col: 0, row: 0, device: { device_id: 2, points: { soc: 20 } } },
    { id: "meter", type: "meter", name: "Meter", col: 1, row: 0, device: { device_id: 3, points: {} } },
    { id: "grid", type: "grid", name: "Grid", col: 2, row: 0 },
  ],
  buses: [],
  connections: [],
};

const bessValues: SldNodeValues = {
  node_id: "bess",
  device_id: 2,
  values: {
    soc: { point_id: 20, value: 68, unit: "%" },
    power: { point_id: 21, value: 4.2, unit: "kW" },
    mode: { point_id: 22, value: 2, label: "discharging" },
  },
  health: { healthy: false, reason: "battery_state is fault" },
};

function rowValues(container: HTMLElement, nodeId: string): Record<string, string> {
  const box = container.querySelector(`[data-info-box="${nodeId}"]`)!;
  return Object.fromEntries(
    [...box.querySelectorAll("[data-row]")].map((row) => [
      row.getAttribute("data-row"),
      row.querySelector("[data-value]")!.textContent,
    ]),
  );
}

describe("SldInfoBox in the diagram", () => {
  const geometry = computeSldGeometry(sld, { showInfoBoxes: true });

  it("draws a box only for linked meter/bess/pv elements", () => {
    const { container } = render(<SiteSldDiagram geometry={geometry} zoom={1} valuesByNode={new Map()} />);
    expect([...container.querySelectorAll("[data-info-box]")].map((box) => box.getAttribute("data-info-box"))).toEqual([
      "bess",
      "meter",
    ]);
  });

  it("shows each value, the enum label and the health verdict with its reason", () => {
    const { container } = render(
      <SiteSldDiagram geometry={geometry} zoom={1} valuesByNode={new Map([["bess", bessValues]])} />,
    );
    expect(rowValues(container, "bess")).toEqual({
      SOC: "68.0 %",
      Power: "4.20 kW",
      Mode: "discharging",
      Health: "Unhealthy",
    });
    expect(container.querySelector('[data-info-box="bess"] title')!.textContent).toBe("battery_state is fault");
  });

  it("shows NA for every value it doesn't have yet", () => {
    const { container } = render(<SiteSldDiagram geometry={geometry} zoom={1} valuesByNode={new Map()} />);
    expect(Object.values(rowValues(container, "meter"))).toEqual(Array(7).fill("NA"));
    expect(rowValues(container, "bess").Health).toBe("NA");
  });

  it("draws no boxes when they are hidden", () => {
    const { container } = render(<SiteSldDiagram geometry={computeSldGeometry(sld)} zoom={1} />);
    expect(container.querySelectorAll("[data-info-box]")).toHaveLength(0);
  });
});
