import { useCallback, useMemo } from "react";
import { PREFERENCE_KEYS, usePreference } from "@/shared/hooks/usePreference";
import { isModbusConfigCache, type ModbusConfigCache } from "../lib/modbusConfigCache";
import type { ModbusLiveStreamRequest } from "@/api/types/modbusStream";
import type { ModbusViewMode } from "../types";

export const MAX_MODBUS_SLOTS = 5;

const NO_CONFIGS: ModbusConfigCache = {};

// The saved stream configs per slot, kept as one of the user's preferences.
export function useModbusConfigSlots() {
  const [configsBySlot, saveConfigs] = usePreference<ModbusConfigCache>(
    PREFERENCE_KEYS.liveDataConfigs, NO_CONFIGS, isModbusConfigCache,
  );

  const saveConfig = useCallback((slot: number, request: ModbusLiveStreamRequest, alias: string, viewMode: ModbusViewMode) => {
    saveConfigs({ ...configsBySlot, [slot]: { alias, request, viewMode } });
  }, [configsBySlot, saveConfigs]);

  const removeConfig = useCallback((slot: number) => {
    if (!(slot in configsBySlot)) return;
    const next = { ...configsBySlot };
    delete next[slot];
    saveConfigs(next);
  }, [configsBySlot, saveConfigs]);

  const clearAllConfigs = useCallback(() => saveConfigs({}), [saveConfigs]);

  const nextFreeSlot = useMemo(() => {
    const used = new Set(Object.keys(configsBySlot).map(Number));
    for (let slot = 1; slot <= MAX_MODBUS_SLOTS; slot++) {
      if (!used.has(slot)) return slot;
    }
    return null;
  }, [configsBySlot]);

  return { configsBySlot, nextFreeSlot, saveConfig, removeConfig, clearAllConfigs };
}
