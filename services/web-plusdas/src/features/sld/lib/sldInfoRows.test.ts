import { describe, expect, it } from "vitest";
import type { SldNodeValues, SldValue } from "@/api/types/sld";
import { INFO_ROWS, NOT_AVAILABLE, formatRowValue, healthState } from "./sldInfoRows";

const value = (overrides: Partial<SldValue>): SldValue => ({ point_id: 1, value: null, ...overrides });

const node = (health: SldNodeValues["health"]): SldNodeValues => ({
  node_id: "bess",
  device_id: 2,
  values: {},
  health,
});

describe("INFO_ROWS", () => {
  it("shows the requested rows, in order, for meter, BESS and PV", () => {
    expect(INFO_ROWS.meter?.map((row) => row.label)).toEqual(["VAB", "VBC", "VCA", "IA", "IB", "IC", "IN"]);
    expect(INFO_ROWS.bess?.map((row) => row.label)).toEqual(["SOC", "Power", "Mode", "Health"]);
    expect(INFO_ROWS.pv?.map((row) => row.label)).toEqual(["Power", "Health", "Sun"]);
  });

  it("gives no box to other element types", () => {
    expect(INFO_ROWS.grid).toBeUndefined();
    expect(INFO_ROWS.inverter).toBeUndefined();
  });
});

describe("formatRowValue", () => {
  it("is NA for an unmapped role, a missing point or a never-read point", () => {
    expect(formatRowValue(null)).toBe(NOT_AVAILABLE);
    expect(formatRowValue(undefined)).toBe(NOT_AVAILABLE);
    expect(formatRowValue(value({ value: null }))).toBe(NOT_AVAILABLE);
  });

  it("shows the number with the value's unit, precision by magnitude", () => {
    expect(formatRowValue(value({ value: 4.2, unit: "kW" }))).toBe("4.20 kW");
    expect(formatRowValue(value({ value: 68, unit: "%" }))).toBe("68.0 %");
    expect(formatRowValue(value({ value: 812.4, unit: "A" }))).toBe("812 A");
  });

  it("falls back to the row's unit, and shows an enum's label instead of its code", () => {
    expect(formatRowValue(value({ value: 230 }), "V")).toBe("230 V");
    expect(formatRowValue(value({ value: 2, label: "discharging" }))).toBe("discharging");
  });

  it("keeps zero as a value, not NA", () => {
    expect(formatRowValue(value({ value: 0, unit: "kW" }))).toBe("0.00 kW");
  });
});

describe("healthState", () => {
  it("maps the profile verdict, with unknown for none", () => {
    expect(healthState(node({ healthy: true }))).toBe("healthy");
    expect(healthState(node({ healthy: false, reason: "fault" }))).toBe("unhealthy");
    expect(healthState(node({ healthy: null }))).toBe("unknown");
    expect(healthState(node(null))).toBe("unknown");
    expect(healthState(undefined)).toBe("unknown");
  });
});
