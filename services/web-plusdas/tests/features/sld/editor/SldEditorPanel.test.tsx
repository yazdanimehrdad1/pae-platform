// @vitest-environment jsdom
import { useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DeviceRecord } from "@/api/types/devices";
import type { SiteSld } from "@/api/types/sld";
import { draftErrors, type Cell } from "@/features/sld/lib/sldDraft";
import { SldEditorPanel, type RequestPick } from "@/features/sld/editor/SldEditorPanel";

const START: SiteSld = {
  schema_version: 1,
  nodes: [{ id: "utility", type: "grid", name: "Utility Grid", col: 0, row: 0 }],
  buses: [{ id: "mv_bus", name: "MV Bus", row: 1, col_start: -1, col_end: 1 }],
  connections: [{ from_id: "utility", to_id: "mv_bus" }],
};

const point = (id: number, name: string, unit: string | null) => ({
  id, name, unit, category: "NATIVE", address: id, size: 1, data_type: "uint16",
  byte_order: "big", word_order: "msw_first", device_id: 2, site_id: 1001,
});

const bessDevice = {
  device_id: 2, site_id: 1001, name: "mock-device-2", type: "BESS", protocol: "Modbus", vendor: null, model: null,
  host: "mock-modbus", port: 502, server_address: 2, poll_enabled: true, read_from_aggregator: true,
  modbus_address_mode: "one_based", scan_ranges: { holding: [], input: [], coils: [] }, scan_ranges_locked: false,
  description: null, created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  points: {
    standardized: [],
    native: [point(20, "state_of_charge", "%"), point(21, "inverter_output_power", "W"), point(22, "battery_state", null)],
    virtual: [],
  },
} as unknown as DeviceRecord;

// Holds the draft like the page does, and exposes the latest one to the test.
function Harness({ onDraft, requestPick = vi.fn() }: { onDraft: (draft: SiteSld) => void; requestPick?: RequestPick }) {
  const [draft, setDraft] = useState(START);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedCell, setSelectedCell] = useState<Cell | null>(null);
  return (
    <SldEditorPanel
      draft={draft}
      onChange={(next) => {
        setDraft(next);
        onDraft(next);
      }}
      devices={[bessDevice]}
      selectedId={selectedId}
      onSelect={setSelectedId}
      selectedCell={selectedCell}
      onClearCell={() => setSelectedCell(null)}
      requestPick={requestPick}
      errors={draftErrors(draft)}
    />
  );
}

const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("SldEditorPanel", () => {
  it("adds a BESS fed from the MV bus, linked to its device with two points mapped", () => {
    let latest = START;
    render(<Harness onDraft={(draft) => (latest = draft)} />);

    change("Type", "bess");
    change("Name", "BESS 1");
    change("Fed from", "mv_bus");
    change("Device", "2");
    change("SOC", "20");
    change("Power", "21");
    fireEvent.click(screen.getByRole("button", { name: "Add element" }));

    const added = latest.nodes.find((node) => node.id === "bess_1");
    expect(added).toMatchObject({ type: "bess", name: "BESS 1", col: -1, row: 2 });
    expect(added?.device).toEqual({ device_id: 2, points: { soc: 20, power: 21 } });
    expect(latest.connections).toContainEqual({ from_id: "mv_bus", to_id: "bess_1" });
    // the new element is selected for editing; its unmapped Mode field shows the NA choice
    expect(screen.getByRole("region", { name: "Selected element" })).toBeTruthy();
    expect((screen.getByLabelText("Mode") as HTMLSelectElement).value).toBe("");
  });

  it("offers only the chosen device's points, and only the fields of the element type", () => {
    render(<Harness onDraft={() => {}} />);
    change("Type", "pv");
    change("Device", "2");
    expect(screen.queryByLabelText("SOC")).toBeNull();
    const power = screen.getByLabelText("Power") as HTMLSelectElement;
    expect([...power.options].map((option) => option.textContent)).toEqual([
      "— none (shows NA) —",
      "state_of_charge (%)",
      "inverter_output_power (W)",
      "battery_state",
    ]);
  });

  it("asks the diagram for a pick when 'Fed from' is picked on the diagram", () => {
    const requestPick = vi.fn<RequestPick>();
    render(<Harness onDraft={() => {}} requestPick={requestPick} />);
    fireEvent.click(screen.getByRole("button", { name: "Fed from: pick on the diagram" }));
    expect(requestPick).toHaveBeenCalledWith("element", "Fed from", expect.any(Function));

    // the page calls back with the clicked element
    act(() => requestPick.mock.calls[0][2]("utility"));
    expect((screen.getByLabelText("Fed from") as HTMLSelectElement).value).toBe("utility");
  });

  it("deletes the selected element and its connections", () => {
    let latest = START;
    render(<Harness onDraft={(draft) => (latest = draft)} />);
    change("Name", "Breaker");
    change("Fed from", "mv_bus");
    fireEvent.click(screen.getByRole("button", { name: "Add element" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(latest.nodes.map((node) => node.id)).toEqual(["utility"]);
    expect(latest.connections).toEqual([{ from_id: "utility", to_id: "mv_bus" }]);
  });

  it("adds a bus fed from the grid", () => {
    let latest = START;
    render(<Harness onDraft={(draft) => (latest = draft)} />);
    fireEvent.click(screen.getByRole("tab", { name: "Add bus" }));
    change("Bus name", "LV Bus");
    change("Bus fed from", "utility");
    fireEvent.click(screen.getByRole("button", { name: "Add bus" }));
    expect(latest.buses?.map((bus) => bus.id)).toEqual(["mv_bus", "lv_bus"]);
    expect(latest.connections).toContainEqual({ from_id: "utility", to_id: "lv_bus" });
  });
});
