// Test data for the alarms page tests: backend-ot records of one site, mapped through the page's
// real mapping (buildSnapshot). Imported only by *.test.ts(x).
import type { AlarmDefinitionRecord, AlarmEventRecord, AlarmSnapshotRecord } from "@/api/types/alarms";
import type { DevicePoint } from "@/api/types/devicePoints";
import type { DeviceRecord } from "@/api/types/devices";
import type { LatestPointReadings } from "@/api/types/historian";
import { buildSnapshot } from "./pageData";

export const NOW = "2026-09-30T12:00:00Z";
const minutesAgo = (minutes: number) => new Date(Date.parse(NOW) - minutes * 60_000).toISOString();

const point = (id: number, name: string, extra: Partial<DevicePoint> = {}): DevicePoint => ({
  id, name, category: "NATIVE", address: id, size: 1, data_type: "uint16", byte_order: "big", word_order: "msw_first",
  device_id: 2, site_id: 1001, unit: null, ...extra,
}) as DevicePoint;

const device = (deviceId: number, name: string, native: DevicePoint[], virtual: DevicePoint[] = []): DeviceRecord => ({
  device_id: deviceId, site_id: 1001, name, type: "BESS", protocol: "Modbus", vendor: "SEL", model: "RTAC",
  host: "mock-modbus", port: 502, server_address: deviceId, poll_enabled: true, read_from_aggregator: true,
  modbus_address_mode: "one_based", scan_ranges: null, scan_ranges_locked: false, description: null,
  created_at: NOW, updated_at: NOW,
  points: { standardized: [], native, virtual },
}) as DeviceRecord;

export const DEVICE_RECORDS: DeviceRecord[] = [
  device(2, "bess-1", [
    point(64, "state_of_charge", { unit: "%" }),
    point(65, "pack_voltage", { unit: "V" }),
    point(66, "faults", { data_type: "bitfield16", bitfield_detail: { "3": "trip" } }),
  ], [point(166, "bess_ready", { category: "VIRTUAL", address: 0, data_type: "enum16", enum_detail: { "0": "not ready", "1": "ready" } })]),
  device(3, "pv-1", [point(70, "ac_power", { device_id: 3, unit: "kW" })]),
];

export const LATEST: Map<number, LatestPointReadings> = new Map([
  [2, {
    meta: { site_id: 1001, device_id: 2, total_count: 3 },
    readings: {
      "64": { id: 64, name: "state_of_charge", data_type: "uint16", unit: "%", value: 15.5, time: minutesAgo(0.25) },
      "65": { id: 65, name: "pack_voltage", data_type: "uint16", unit: "V", value: 398.4, time: minutesAgo(0.25) },
      "166": { id: 166, name: "bess_ready", data_type: "enum16", value: 1, time: minutesAgo(0.25) },
    },
  }],
  [3, { meta: { site_id: 1001, device_id: 3, total_count: 0 }, readings: {} }],
]);

const definition = (id: number, name: string, extra: Partial<AlarmDefinitionRecord>): AlarmDefinitionRecord => ({
  id, site_id: 1001, source: "USER", profile_alarm_key: null, name, kind: "threshold", rule: null, severity: "warning",
  message: "", enabled: true, notify_mobile: false, notify_email: false,
  created_at: "2026-09-29T08:00:00Z", updated_at: "2026-09-30T09:00:00Z", deleted_at: null, ...extra,
});

export const DEFINITIONS: AlarmDefinitionRecord[] = [
  definition(1, "bess_soc_low", {
    severity: "fault", message: "BESS SOC low", notify_mobile: true,
    rule: { kind: "threshold", delay_sec: 60, deadband: 2,
      condition: { type: "condition", point_id: 64, operator: "<", value: 20, compare_point_id: null, bit: null } },
  }),
  definition(2, "pv_comms_lost", {
    kind: "comms_stale", rule: { kind: "comms_stale", device_id: 3, stale_after_sec: 60 },
  }),
  definition(3, "pv_inverter_offline", {
    source: "PROFILE", profile_alarm_key: "inverter_offline", kind: "profile",
    message: "PV inverter is not producing",
  }),
  definition(4, "bess_trip_while_ready", {
    kind: "condition", enabled: false,
    rule: { kind: "condition", delay_sec: 30, when: { type: "group", match: "all", items: [
      { type: "condition", point_id: 66, operator: "bit_set", value: null, compare_point_id: null, bit: 3 },
      { type: "condition", point_id: 166, operator: "==", value: 1, compare_point_id: null, bit: null },
    ] } },
  }),
];

const event = (id: number, definitionId: number, extra: Partial<AlarmEventRecord>): AlarmEventRecord => ({
  id, definition_id: definitionId, site_id: 1001, device_id: null, severity: "warning", raised_at: minutesAgo(5),
  cleared_at: null, value_at_raise: null, message: "", ...extra,
});

export const EVENTS: AlarmEventRecord[] = [
  event(101, 1, { device_id: 2, severity: "fault", raised_at: minutesAgo(8), value_at_raise: 18, message: "BESS SOC low" }),
  event(102, 3, { device_id: 3, severity: "warning", raised_at: minutesAgo(20), value_at_raise: 6, message: "PV inverter is not producing" }),
  event(103, 2, { device_id: 3, raised_at: minutesAgo(90), cleared_at: minutesAgo(60), message: "pv-1: no successful poll" }),
];

export const SNAPSHOT_RECORD: AlarmSnapshotRecord = {
  site_id: 1001,
  now: NOW,
  definitions: DEFINITIONS,
  events: EVENTS,
  log: [
    { id: "101:raised", event_id: 101, definition_id: 1, device_id: 2, kind: "raised", severity: "fault", at: minutesAgo(8), message: "BESS SOC low" },
    { id: "103:cleared", event_id: 103, definition_id: 2, device_id: 3, kind: "cleared", severity: "warning", at: minutesAgo(60), message: "pv_comms_lost cleared" },
  ],
};

export const testSnapshot = () => buildSnapshot(SNAPSHOT_RECORD, DEVICE_RECORDS, LATEST);
