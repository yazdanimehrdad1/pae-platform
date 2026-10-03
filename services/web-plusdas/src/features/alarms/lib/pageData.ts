import type { AlarmDefinitionRecord, AlarmEventRecord, AlarmLogRecord, AlarmSnapshotRecord } from "@/api/types/alarms";
import type { DevicePoint } from "@/api/types/devicePoints";
import type { DevicePointsEntry, DeviceRecord } from "@/api/types/devices";
import type { LatestPointReadings } from "@/api/types/historian";
import { devicePointOptions } from "@/shared/components/conditions/devicePointOptions";
import type { AlarmEvent, AlarmLogEntry, AlarmSnapshot, Device, Point, Rule } from "../types";

// backend-ot records → the page model. Pure, so the page and its tests share one mapping.

const idOrNull = (id: number | null | undefined) => (id == null ? null : String(id));

export function toRule(record: AlarmDefinitionRecord): Rule {
  return {
    id: String(record.id),
    name: record.name,
    source: record.source,
    kind: record.kind,
    rule: record.rule ?? null,
    profileKey: record.profile_alarm_key ?? null,
    severity: record.severity,
    message: record.message,
    enabled: record.enabled,
    notify: { mobile: record.notify_mobile, email: record.notify_email },
    createdAt: record.created_at,
    updatedAt: record.updated_at,
  };
}

export function toEvent(record: AlarmEventRecord): AlarmEvent {
  return {
    id: String(record.id),
    ruleId: String(record.definition_id),
    deviceId: idOrNull(record.device_id),
    severity: record.severity,
    raisedAt: record.raised_at,
    clearedAt: record.cleared_at ?? null,
    valueAtRaise: record.value_at_raise ?? null,
    message: record.message,
  };
}

function toLogEntry(record: AlarmLogRecord): AlarmLogEntry {
  return {
    id: record.id,
    eventId: String(record.event_id),
    ruleId: String(record.definition_id),
    deviceId: idOrNull(record.device_id),
    kind: record.kind,
    severity: record.severity,
    at: record.at,
    message: record.message,
  };
}

const byPointName = (left: DevicePoint, right: DevicePoint) =>
  left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: "base" });
const sortedPoints = (points: DevicePoint[] | undefined) => [...(points ?? [])].sort(byPointName);

/** A device's points as the asset tree and the condition picker list them: standardized, virtual, native, each by name. */
function toPointsEntry(device: DeviceRecord): DevicePointsEntry {
  const groups = {
    standardized: sortedPoints(device.points.standardized), virtual: sortedPoints(device.points.virtual), native: sortedPoints(device.points.native),
  };
  return { deviceId: device.device_id, deviceName: device.name, groups, points: [...groups.standardized, ...groups.virtual, ...groups.native] };
}

function toPoints(device: DeviceRecord, latest: LatestPointReadings | undefined): Point[] {
  const entry = toPointsEntry(device);
  const options = new Map(devicePointOptions([entry], { includeVirtual: true }).map(option => [option.id, option]));
  return entry.points.map(point => {
    const reading = latest?.readings[String(point.id)];
    return {
      ...options.get(String(point.id))!,
      deviceId: String(device.device_id),
      register: point.category === "NATIVE" ? point.address ?? null : null,
      category: point.category as Point["category"],
      value: reading?.value ?? null,
      updatedAt: reading?.value != null ? reading.time ?? null : null,
    };
  });
}

/** The newest reading time among the device's native points: its last successful poll. */
function lastPollAt(points: Point[]): string | null {
  const times = points.filter(point => point.category === "NATIVE" && point.updatedAt).map(point => point.updatedAt!);
  return times.length ? times.reduce((newest, time) => (Date.parse(time) > Date.parse(newest) ? time : newest)) : null;
}

export function buildSnapshot(
  snapshot: AlarmSnapshotRecord,
  deviceRecords: DeviceRecord[],
  latestByDevice: Map<number, LatestPointReadings>,
): AlarmSnapshot {
  const devices: Device[] = [];
  const points: Point[] = [];
  for (const record of deviceRecords) {
    const devicePoints = toPoints(record, latestByDevice.get(record.device_id));
    points.push(...devicePoints);
    devices.push({
      id: String(record.device_id),
      name: record.name,
      protocol: record.protocol,
      host: record.host,
      port: record.port,
      unitId: record.server_address,
      lastPollAt: lastPollAt(devicePoints),
    });
  }
  return {
    siteId: String(snapshot.site_id),
    now: Date.parse(snapshot.now),
    devices,
    points,
    rules: snapshot.definitions.map(toRule),
    events: snapshot.events.map(toEvent),
    log: snapshot.log.map(toLogEntry),
  };
}
