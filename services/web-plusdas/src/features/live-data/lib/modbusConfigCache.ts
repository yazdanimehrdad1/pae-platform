import type { ModbusLiveStreamRequest } from "@/api/types/modbusStream";
import type { ModbusViewMode } from "../types";

// The Modbus stream configs the user saved per slot: one of the user's preferences
// (PREFERENCE_KEYS.liveDataConfigs), so they follow the user to any browser.
export interface ModbusConfigEntry {
  alias: string;
  request: ModbusLiveStreamRequest;
  // Missing in configs saved before view modes existed: read as "live".
  viewMode?: ModbusViewMode;
}

export type ModbusConfigCache = Record<number, ModbusConfigEntry>;

export function isModbusConfigCache(value: unknown): value is ModbusConfigCache {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
