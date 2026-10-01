import type { DevicePointsEntry } from "@/api/types/devices";
import { isBitfieldPoint, isEnumPoint, sortedBits } from "@/shared/lib/discretePoints";
import type { ConditionPointOption } from "./conditionModel";

/**
 * A site's real device points (backend-ot, from `devicesApi.getBySiteWithPoints`) as condition
 * picker options, grouped by device, in the asset tree's order. Virtual points are left out unless
 * `includeVirtual`: a virtual point can't read another virtual point, but an alarm rule can watch one.
 */
export function devicePointOptions(devices: DevicePointsEntry[], { includeVirtual = false } = {}): ConditionPointOption[] {
  return devices.flatMap(device => device.points
    .filter(point => includeVirtual || point.category !== "VIRTUAL")
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
        hint: point.category === "NATIVE" ? undefined : point.category.toLowerCase(),
      } satisfies ConditionPointOption;
    }));
}
