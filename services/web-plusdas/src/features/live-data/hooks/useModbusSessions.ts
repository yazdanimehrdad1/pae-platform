import { useCallback, useEffect, useRef, useState } from "react";
import { modbusStreamApi } from "@/api";
import type { SseEvent } from "@/api/sse";
import { useAuth } from "@/shared/contexts/auth";
import {
  clearModbusSessionCache,
  loadModbusSessionCache,
  saveModbusSessionCache,
  type CachedSessionMeta,
} from "../lib/modbusSessionStorage";
import type {
  ModbusConnectedEvent,
  ModbusDoneEvent,
  ModbusLiveStreamRequest,
  ModbusPollEvent,
  ModbusSessionState,
} from "@/shared/types/modbusLiveStream";

export function useModbusSessions() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<ModbusSessionState[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const cacheRef = useRef<Record<string, CachedSessionMeta>>({});

  useEffect(() => {
    if (user?.id) cacheRef.current = loadModbusSessionCache(user.id);
  }, [user?.id]);

  const persistCache = () => {
    if (user?.id) saveModbusSessionCache(user.id, cacheRef.current);
  };

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const summaries = await modbusStreamApi.list();
      setSessions(prev => {
        const prevById = new Map(prev.map(s => [s.sessionId, s]));
        const knownSlots = summaries.map(summary => {
          const existing = prevById.get(summary.session_id);
          const cached = cacheRef.current[summary.session_id];
          return existing?.slot ?? cached?.slot ?? null;
        });
        const usedSlots = new Set(knownSlots.filter((slot): slot is number => slot != null));
        let nextFallbackSlot = 1;
        const resolveFallbackSlot = (): number => {
          while (usedSlots.has(nextFallbackSlot)) nextFallbackSlot++;
          usedSlots.add(nextFallbackSlot);
          return nextFallbackSlot;
        };
        return summaries.map((summary, i) => {
          const existing = prevById.get(summary.session_id);
          const cached = cacheRef.current[summary.session_id];
          return {
            sessionId: summary.session_id,
            slot: knownSlots[i] ?? resolveFallbackSlot(),
            host: summary.host,
            port: summary.port,
            server_address: summary.server_address,
            kind: summary.kind,
            start_address: summary.start_address,
            end_address: summary.end_address,
            modbus_address_mode: summary.modbus_address_mode,
            interval: summary.interval,
            duration: summary.duration,
            serverStatus: summary.status,
            attachment: existing?.attachment ?? 'idle',
            pollCount: existing?.pollCount ?? 0,
            lastTimestamp: existing?.lastTimestamp ?? null,
            registers: existing?.registers ?? {},
            error: existing?.error ?? null,
            registerConfigs: existing?.registerConfigs ?? cached?.registerConfigs ?? {},
            startedAt: existing?.startedAt ?? cached?.startedAt ?? null,
          };
        });
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const controllers = abortControllersRef.current;
    return () => {
      controllers.forEach(controller => controller.abort());
      controllers.clear();
    };
  }, []);

  const handlePollOrDone = (sessionId: string, evt: SseEvent) => {
    if (evt.event === 'poll') {
      const data = JSON.parse(evt.data) as ModbusPollEvent;
      setSessions(prev => prev.map(s => s.sessionId === sessionId
        ? { ...s, attachment: 'streaming', pollCount: data.poll, lastTimestamp: data.timestamp, registers: data.registers }
        : s));
    } else if (evt.event === 'done') {
      const data = JSON.parse(evt.data) as ModbusDoneEvent;
      setSessions(prev => prev.map(s => s.sessionId === sessionId
        ? { ...s, serverStatus: 'done', pollCount: data.total_polls }
        : s));
    }
  };

  const finishAttach = (sessionId: string, err: unknown) => {
    abortControllersRef.current.delete(sessionId);
    if (err && (err as Error).name === 'AbortError') return;
    setSessions(prev => prev.map(s => {
      if (s.sessionId !== sessionId) return s;
      if (err) return { ...s, attachment: 'error', error: (err as Error).message };
      return s.attachment === 'streaming' ? { ...s, attachment: 'idle' } : s;
    }));
  };

  const startSession = (slot: number, request: ModbusLiveStreamRequest): Promise<string> => {
    const controller = new AbortController();
    let sessionId: string | null = null;

    return new Promise<string>((resolve, reject) => {
      const onEvent = (evt: SseEvent) => {
        if (evt.event === 'connected') {
          const data = JSON.parse(evt.data) as ModbusConnectedEvent;
          const newSessionId = data.session_id;
          sessionId = newSessionId;
          abortControllersRef.current.set(newSessionId, controller);
          const startedAt = new Date().toISOString();
          cacheRef.current = { ...cacheRef.current, [newSessionId]: { slot, registerConfigs: request.register_configs, startedAt } };
          persistCache();
          setSessions(prev => [...prev, {
            sessionId: newSessionId,
            slot,
            host: request.host,
            port: request.port,
            server_address: request.server_address,
            kind: request.kind,
            start_address: request.start_address,
            end_address: request.end_address,
            modbus_address_mode: request.modbus_address_mode,
            interval: request.interval,
            duration: request.duration,
            serverStatus: 'active',
            attachment: 'streaming',
            pollCount: 0,
            lastTimestamp: null,
            registers: {},
            registerConfigs: request.register_configs,
            error: null,
            startedAt,
          }]);
          resolve(newSessionId);
        } else if (sessionId) {
          handlePollOrDone(sessionId, evt);
        }
      };

      modbusStreamApi.start(request, onEvent, controller.signal)
        .then(() => { if (sessionId) finishAttach(sessionId, null); })
        .catch((err) => {
          if (sessionId) finishAttach(sessionId, err);
          else reject(err);
        });
    });
  };

  const relaunchSlot = async (slot: number, request: ModbusLiveStreamRequest): Promise<string> => {
    const existing = sessions.find(s => s.slot === slot);
    if (existing) await deleteSession(existing.sessionId);
    return startSession(slot, request);
  };

  const resumeSession = (sessionId: string) => {
    const controller = new AbortController();
    abortControllersRef.current.set(sessionId, controller);
    setSessions(prev => prev.map(s => s.sessionId === sessionId ? { ...s, attachment: 'connecting', error: null } : s));

    modbusStreamApi.resume(sessionId, (evt) => handlePollOrDone(sessionId, evt), controller.signal)
      .then(() => finishAttach(sessionId, null))
      .catch((err) => finishAttach(sessionId, err));
  };

  const stopSession = async (sessionId: string) => {
    abortControllersRef.current.get(sessionId)?.abort();
    abortControllersRef.current.delete(sessionId);
    setSessions(prev => prev.map(s => s.sessionId === sessionId ? { ...s, attachment: 'idle', serverStatus: 'stopped' } : s));
    await modbusStreamApi.stop(sessionId).catch(() => {});
    refresh();
  };

  const deleteSession = async (sessionId: string) => {
    abortControllersRef.current.get(sessionId)?.abort();
    abortControllersRef.current.delete(sessionId);
    await modbusStreamApi.delete(sessionId).catch(() => {});
    setSessions(prev => prev.filter(s => s.sessionId !== sessionId));
    if (cacheRef.current[sessionId]) {
      const nextCache = { ...cacheRef.current };
      delete nextCache[sessionId];
      cacheRef.current = nextCache;
      persistCache();
    }
  };

  const deleteAllSessions = async () => {
    abortControllersRef.current.forEach(controller => controller.abort());
    abortControllersRef.current.clear();
    await modbusStreamApi.deleteAll().catch(() => {});
    setSessions([]);
    cacheRef.current = {};
    if (user?.id) clearModbusSessionCache(user.id);
  };

  return { sessions, refresh, isLoading, relaunchSlot, resumeSession, stopSession, deleteSession, deleteAllSessions };
}
