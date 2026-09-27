import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alarmSource } from "../data/source";
import type { HistoryFilter, Rule } from "../types";

const ALARMS_KEY = ["alarms"] as const;

/** Current alarm state; refetched whenever the source reports a change. */
export function useAlarmSnapshot() {
  const queryClient = useQueryClient();
  useEffect(
    () => alarmSource.subscribe(() => queryClient.invalidateQueries({ queryKey: ALARMS_KEY })),
    [queryClient],
  );
  return useQuery({ queryKey: [...ALARMS_KEY, "snapshot"], queryFn: () => alarmSource.getSnapshot() });
}

export function usePointSeries(pointId: string | null, from: number, to: number) {
  // Rounded to the minute so each 5 s tick doesn't create a new cache entry.
  const fromMinute = Math.floor(from / 60_000);
  return useQuery({
    queryKey: [...ALARMS_KEY, "series", pointId, fromMinute, to - from],
    queryFn: () => alarmSource.getSeries(pointId!, from, to),
    enabled: pointId !== null,
    placeholderData: previous => previous,
  });
}

export function useAlarmHistory(filter: HistoryFilter, enabled: boolean) {
  return useQuery({
    queryKey: [...ALARMS_KEY, "history", filter],
    queryFn: () => alarmSource.queryEvents(filter),
    enabled,
  });
}


export function useSaveRule() {
  return useMutation({ mutationFn: (rule: Rule) => alarmSource.saveRule(rule) });
}
