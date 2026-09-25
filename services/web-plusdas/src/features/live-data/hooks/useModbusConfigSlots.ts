import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/shared/contexts/auth";
import {
  clearModbusConfigCache,
  loadModbusConfigCache,
  saveModbusConfigCache,
  type ModbusConfigCache,
} from "../lib/modbusConfigStorage";
import type { ModbusLiveStreamRequest } from "@/shared/types/modbusLiveStream";

export const MAX_MODBUS_SLOTS = 5;

export function useModbusConfigSlots() {
  const { user } = useAuth();
  const [configsBySlot, setConfigsBySlot] = useState<ModbusConfigCache>({});

  useEffect(() => {
    if (user?.id) setConfigsBySlot(loadModbusConfigCache(user.id));
  }, [user?.id]);

  const saveConfig = useCallback((slot: number, request: ModbusLiveStreamRequest, alias: string) => {
    setConfigsBySlot(prev => {
      const next = { ...prev, [slot]: { alias, request } };
      if (user?.id) saveModbusConfigCache(user.id, next);
      return next;
    });
  }, [user?.id]);

  const removeConfig = useCallback((slot: number) => {
    setConfigsBySlot(prev => {
      if (!(slot in prev)) return prev;
      const next = { ...prev };
      delete next[slot];
      if (user?.id) saveModbusConfigCache(user.id, next);
      return next;
    });
  }, [user?.id]);

  const clearAllConfigs = useCallback(() => {
    setConfigsBySlot({});
    if (user?.id) clearModbusConfigCache(user.id);
  }, [user?.id]);

  const nextFreeSlot = useMemo(() => {
    const used = new Set(Object.keys(configsBySlot).map(Number));
    for (let slot = 1; slot <= MAX_MODBUS_SLOTS; slot++) {
      if (!used.has(slot)) return slot;
    }
    return null;
  }, [configsBySlot]);

  return { configsBySlot, nextFreeSlot, saveConfig, removeConfig, clearAllConfigs };
}
