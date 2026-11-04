import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { useQuery } from "@tanstack/react-query";
import { meApi } from "@/api/me";
import { toast } from "@/shared/hooks/use-toast";
import type { Trend } from "../types";
import { fromSavedTrend, sameDefinition, toDefinition } from "../lib/savedTrends";

export const SAVED_TRENDS_QUERY_KEY = ["me", "trends"] as const;
// Edits to one trend (points toggled one by one, styles dragged) are saved once they settle.
const SAVE_DELAY_MS = 400;
const DEFAULT_TREND_NAME = "Default Trend";

// Saves go out one at a time, in order, for the whole app: a page that opens again reloads the
// trends only after the saves the last visit queued.
let saveQueue: Promise<unknown> = Promise.resolve();

// The user's saved trends, kept by intelli-gateway so they follow the user to any browser. The
// page edits `trends` like local state; every change is saved in the background: deletes at
// once, edits per trend after SAVE_DELAY_MS, then the order. New trends go through createTrend,
// which saves first so the trend has its server id. A user with no trends gets one empty
// "Default Trend", as before.
export function useSavedTrends(): {
  trends: Trend[];
  setTrends: Dispatch<SetStateAction<Trend[]>>;
  createTrend: (name: string) => Promise<Trend>;
  isLoaded: boolean;
} {
  // Fetched fresh each time the page opens (after the queued saves), never on focus.
  const { data, isSuccess, isFetching } = useQuery({
    queryKey: SAVED_TRENDS_QUERY_KEY,
    queryFn: async () => {
      await saveQueue;
      return meApi.listTrends();
    },
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
  });
  const [trends, setTrends] = useState<Trend[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  // What the server holds (as far as this page knows), in its order.
  const syncedRef = useRef<Trend[] | null>(null);
  const timersRef = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  // Edits waiting for their delay, by trend id: sent at once if the page closes first.
  const pendingRef = useRef(new Map<string, Trend>());

  // One save at a time, in order; a failure is reported and doesn't stop the next one.
  const enqueue = useCallback((save: () => Promise<unknown>) => {
    saveQueue = saveQueue.then(save).catch((error) => {
      console.warn("Could not save the trends", error);
      toast({ title: "Trends not saved", description: "A change to your trends could not be saved.", variant: "destructive" });
    });
  }, []);

  const createTrend = useCallback(async (name: string) => {
    const created = fromSavedTrend(await meApi.createTrend(toDefinition({ id: "", name, points: [] })));
    syncedRef.current = [...(syncedRef.current ?? []), created];
    setTrends(previous => [...previous, created]);
    return created;
  }, []);

  useEffect(() => {
    if (!isSuccess || isFetching || syncedRef.current !== null) return;
    const loaded = (Array.isArray(data) ? data : []).map(fromSavedTrend);
    syncedRef.current = loaded;
    setTrends(loaded);
    setIsLoaded(true);
    if (loaded.length === 0) {
      createTrend(DEFAULT_TREND_NAME).catch(error => console.warn("Could not create the default trend", error));
    }
  }, [isSuccess, isFetching, data, createTrend]);

  useEffect(() => {
    const synced = syncedRef.current;
    if (synced === null) return;
    const currentIds = new Set(trends.map(trend => trend.id));
    const syncedById = new Map(synced.map(trend => [trend.id, trend]));

    for (const trend of synced) {
      if (currentIds.has(trend.id)) continue;
      clearTimeout(timersRef.current.get(trend.id));
      timersRef.current.delete(trend.id);
      pendingRef.current.delete(trend.id);
      enqueue(() => meApi.deleteTrend(Number(trend.id)));
    }
    for (const trend of trends) {
      const before = syncedById.get(trend.id);
      if (!before || sameDefinition(before, trend)) continue;
      clearTimeout(timersRef.current.get(trend.id));
      pendingRef.current.set(trend.id, trend);
      timersRef.current.set(trend.id, setTimeout(() => {
        timersRef.current.delete(trend.id);
        pendingRef.current.delete(trend.id);
        enqueue(() => meApi.updateTrend(Number(trend.id), toDefinition(trend)));
      }, SAVE_DELAY_MS));
    }
    const kept = trends.filter(trend => syncedById.has(trend.id));
    const keptOrder = kept.map(trend => trend.id);
    const syncedOrder = synced.filter(trend => currentIds.has(trend.id)).map(trend => trend.id);
    if (keptOrder.join(",") !== syncedOrder.join(",")) {
      enqueue(() => meApi.reorderTrends(keptOrder.map(Number)));
    }
    syncedRef.current = kept;
  }, [trends, enqueue]);

  // Leaving the page: send the edits still waiting for their delay.
  useEffect(() => {
    const timers = timersRef.current;
    const pending = pendingRef.current;
    return () => {
      timers.forEach(timer => clearTimeout(timer));
      timers.clear();
      pending.forEach(trend => enqueue(() => meApi.updateTrend(Number(trend.id), toDefinition(trend))));
      pending.clear();
    };
  }, [enqueue]);

  return { trends, setTrends, createTrend, isLoaded };
}
