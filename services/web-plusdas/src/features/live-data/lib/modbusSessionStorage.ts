import type { ModbusRegisterConfig } from "@/shared/types/modbusLiveStream";

export interface CachedSessionMeta {
  slot: number;
  registerConfigs: Record<string, ModbusRegisterConfig>;
  startedAt: string;
}

type ModbusSessionCache = Record<string, CachedSessionMeta>;

const STORAGE_KEY_PREFIX = "modbus_session_cache_";

function getStorageKey(userId: string): string {
  return `${STORAGE_KEY_PREFIX}${userId}`;
}

export function loadModbusSessionCache(userId: string): ModbusSessionCache {
  try {
    const stored = localStorage.getItem(getStorageKey(userId));
    if (!stored) return {};
    const cache = JSON.parse(stored) as ModbusSessionCache;
    if (typeof cache !== 'object' || cache === null || Array.isArray(cache)) return {};
    return cache;
  } catch {
    return {};
  }
}

export function saveModbusSessionCache(userId: string, cache: ModbusSessionCache): void {
  try {
    localStorage.setItem(getStorageKey(userId), JSON.stringify(cache));
  } catch (error) {
    console.error('Error saving modbus session cache:', error);
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      console.warn('localStorage quota exceeded.');
    }
  }
}

export function clearModbusSessionCache(userId: string): void {
  try {
    localStorage.removeItem(getStorageKey(userId));
  } catch (error) {
    console.error('Error clearing modbus session cache:', error);
  }
}
