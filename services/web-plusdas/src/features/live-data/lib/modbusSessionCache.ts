import type { ModbusRegisterConfig } from "@/api/types/modbusStream";
import type { ModbusViewMode } from "../types";

// What the UI remembers about each running stream session (its slot, register configs, view
// mode): one of the user's preferences (PREFERENCE_KEYS.liveDataSessions).
export interface CachedSessionMeta {
  slot: number;
  registerConfigs: Record<string, ModbusRegisterConfig>;
  startedAt: string;
  // Missing in sessions cached before view modes existed: read as "live".
  viewMode?: ModbusViewMode;
}

export type ModbusSessionCache = Record<string, CachedSessionMeta>;

export function isModbusSessionCache(value: unknown): value is ModbusSessionCache {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
