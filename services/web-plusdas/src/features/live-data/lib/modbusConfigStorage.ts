import type { ModbusLiveStreamRequest } from "@/shared/types/modbusLiveStream";

export interface ModbusConfigEntry {
  alias: string;
  request: ModbusLiveStreamRequest;
}

export type ModbusConfigCache = Record<number, ModbusConfigEntry>;

const STORAGE_KEY_PREFIX = "modbus_config_cache_";

function getStorageKey(userId: string): string {
  return `${STORAGE_KEY_PREFIX}${userId}`;
}

export function loadModbusConfigCache(userId: string): ModbusConfigCache {
  try {
    const stored = localStorage.getItem(getStorageKey(userId));
    if (!stored) return {};
    const cache = JSON.parse(stored) as ModbusConfigCache;
    if (typeof cache !== 'object' || cache === null || Array.isArray(cache)) return {};
    return cache;
  } catch {
    return {};
  }
}

export function saveModbusConfigCache(userId: string, cache: ModbusConfigCache): void {
  try {
    localStorage.setItem(getStorageKey(userId), JSON.stringify(cache));
  } catch (error) {
    console.error('Error saving modbus config cache:', error);
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      console.warn('localStorage quota exceeded.');
    }
  }
}

export function clearModbusConfigCache(userId: string): void {
  try {
    localStorage.removeItem(getStorageKey(userId));
  } catch (error) {
    console.error('Error clearing modbus config cache:', error);
  }
}
