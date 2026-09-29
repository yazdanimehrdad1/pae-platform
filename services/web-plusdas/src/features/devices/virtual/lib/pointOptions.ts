import type { DevicePointsEntry } from "@/api/types/devices";
import type { ConditionPointOption } from "@/shared/components/conditions/conditionModel";
import { isBitfieldPoint, isEnumPoint, sortedBits } from "@/shared/lib/discretePoints";

/**
 * The points a virtual point can read: every non-virtual point on the site, grouped by device.
 * (backend-ot rejects a virtual input, so they aren't offered.)
 */
export function toConditionPointOptions(devices: DevicePointsEntry[]): ConditionPointOption[] {
  return devices.flatMap(device => device.points
    .filter(point => point.category !== "VIRTUAL")
    .map(point => {
      const kind = isBitfieldPoint(point) ? "bitfield" : isEnumPoint(point) ? "enum" : "numeric";
      return {
        id: String(point.id),
        name: point.name,
        label: `${device.deviceName} · ${point.name}`,
        group: device.deviceName,
        kind,
        unit: point.unit,
        states: kind === "enum"
          ? Object.entries(point.enum_detail ?? {})
            .map(([value, label]) => ({ value: Number(value), label }))
            .filter(state => Number.isFinite(state.value))
            .sort((left, right) => left.value - right.value)
          : undefined,
        bits: kind === "bitfield" ? sortedBits(point.bitfield_detail) : undefined,
        hint: point.category === "STANDARDIZED" ? "standardized" : undefined,
      } satisfies ConditionPointOption;
    }));
}
