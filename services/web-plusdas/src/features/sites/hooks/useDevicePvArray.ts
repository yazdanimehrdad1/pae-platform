import { useQuery } from "@tanstack/react-query";
import { devicesApi } from "@/api";
import type { PvArrayConfig, PvArrayConfigRequest } from "@/api/types/devices";

// Device types that can carry a PV array (backend-ot refuses the others with 400).
export const PV_ARRAY_DEVICE_TYPES: ReadonlySet<string> = new Set(["PV", "INVERTER"]);

export function supportsPvArray(deviceType: string | undefined): boolean {
  return deviceType !== undefined && PV_ARRAY_DEVICE_TYPES.has(deviceType.toUpperCase());
}

export const pvArrayKey = (siteId: string | undefined, deviceId: number | undefined) =>
  ["pv-array", siteId, deviceId];

/** The PV array of an existing PV/INVERTER device (null: none configured). Loads only when
 * `enabled` (e.g. while the edit dialog is open). */
export function useDevicePvArray(
  siteId: string | undefined,
  device: { device_id: number; type: string } | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: pvArrayKey(siteId, device?.device_id),
    queryFn: () => devicesApi.getPvArray(siteId as string, (device as { device_id: number }).device_id),
    enabled: enabled && !!siteId && !!device && supportsPvArray(device.type),
  });
}

/** Apply the form's PV array to the device: save it, or delete the existing one when the form
 * has none (fields cleared, or the device is no longer PV/INVERTER). */
export async function savePvArray(
  siteId: string,
  deviceId: number,
  pvArray: PvArrayConfigRequest | null,
  existing: PvArrayConfig | null | undefined,
): Promise<void> {
  if (pvArray) {
    await devicesApi.putPvArray(siteId, deviceId, pvArray);
  } else if (existing) {
    await devicesApi.deletePvArray(siteId, deviceId);
  }
}
