import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { alarmsApi, devicesApi, historianApi } from "@/api";
import type { AlarmDefinitionCreateRequest, AlarmDefinitionUpdateRequest, AlarmSnapshotRecord } from "@/api/types/alarms";
import type { LatestPointReadings } from "@/api/types/historian";
import { buildSnapshot, toEvent } from "../lib/pageData";
import type { AlarmSnapshot, HistoryFilter, Point, Rule, Sample } from "../types";

// backend-ot evaluates alarms every poll interval; the page polls at about the same pace.
export const REFRESH_MS = 10_000;
const DEVICES_STALE_MS = 60_000;

const alarmsKey = (siteId: string) => ["alarms", siteId] as const;

/** The page's data for one site: alarms snapshot, devices and their points, latest values. Refetched every 10 s. */
export function useAlarmSnapshot(siteId: string | null) {
  const enabled = !!siteId;
  const snapshot = useQuery({
    queryKey: [...alarmsKey(siteId ?? ""), "snapshot"],
    queryFn: () => alarmsApi.getSnapshot(siteId!),
    enabled,
    refetchInterval: REFRESH_MS,
  });
  const devices = useQuery({
    queryKey: [...alarmsKey(siteId ?? ""), "devices"],
    queryFn: () => devicesApi.getRecords(siteId!),
    enabled,
    staleTime: DEVICES_STALE_MS,
    refetchInterval: DEVICES_STALE_MS,
  });
  const deviceIds = (devices.data ?? []).map(device => device.device_id);
  const latest = useQuery({
    queryKey: [...alarmsKey(siteId ?? ""), "latest", deviceIds],
    queryFn: async () => {
      const readings = await Promise.all(deviceIds.map(deviceId => historianApi.getLatestReadings(siteId!, String(deviceId))));
      return new Map<number, LatestPointReadings>(deviceIds.map((deviceId, index) => [deviceId, readings[index]]));
    },
    enabled: enabled && devices.isSuccess,
    refetchInterval: REFRESH_MS,
    placeholderData: previous => previous,
  });

  const data = useMemo<AlarmSnapshot | undefined>(
    () => (snapshot.data && devices.data ? buildSnapshot(snapshot.data, devices.data, latest.data ?? new Map()) : undefined),
    [snapshot.data, devices.data, latest.data],
  );
  return { data, isLoading: snapshot.isLoading || devices.isLoading, error: snapshot.error ?? devices.error };
}

/** Stored readings of one numeric point, oldest first. */
export function usePointSeries(siteId: string, point: Point | null, from: number, to: number) {
  // Rounded to the minute so each refresh doesn't create a new cache entry.
  const fromMinute = Math.floor(from / 60_000);
  return useQuery({
    queryKey: [...alarmsKey(siteId), "series", point?.id, fromMinute, to - from],
    queryFn: async (): Promise<Sample[]> => {
      const response = await historianApi.getDevicePointReadings({
        siteId, deviceId: point!.deviceId, pointIds: [point!.id],
        startTime: new Date(fromMinute * 60_000).toISOString(), endTime: new Date(to).toISOString(),
      });
      return (response.readings[point!.id]?.timeseries ?? [])
        .filter(reading => reading.value != null)
        .map(reading => ({ t: Date.parse(reading.time), v: reading.value! }));
    },
    enabled: point !== null,
    refetchInterval: REFRESH_MS,
    placeholderData: previous => previous,
  });
}

export function useAlarmHistory(siteId: string, filter: HistoryFilter, enabled: boolean) {
  return useQuery({
    queryKey: [...alarmsKey(siteId), "history", filter],
    queryFn: async () => (await alarmsApi.queryEvents(siteId, {
      startTime: new Date(filter.from).toISOString(),
      endTime: new Date(filter.to).toISOString(),
      deviceId: filter.deviceId ? Number(filter.deviceId) : undefined,
      severity: filter.severity,
      definitionId: filter.ruleId ? Number(filter.ruleId) : undefined,
    })).map(toEvent),
    enabled,
  });
}

/**
 * Create, change and delete alarms; each refetches the site's snapshot. A change shows at once
 * (optimistic) and rolls back if backend-ot rejects it, so a switch never sits in its old position
 * while the save is in flight (a second click would otherwise send the same value again).
 */
export function useRuleMutations(siteId: string) {
  const queryClient = useQueryClient();
  const snapshotKey = [...alarmsKey(siteId), "snapshot"];
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: snapshotKey });
  const create = useMutation({ mutationFn: (request: AlarmDefinitionCreateRequest) => alarmsApi.create(siteId, request), onSuccess });
  const update = useMutation({
    mutationFn: ({ rule, patch }: { rule: Rule; patch: AlarmDefinitionUpdateRequest }) => alarmsApi.update(siteId, Number(rule.id), patch),
    onMutate: async ({ rule, patch }) => {
      await queryClient.cancelQueries({ queryKey: snapshotKey });
      const previous = queryClient.getQueryData<AlarmSnapshotRecord>(snapshotKey);
      const changes = Object.fromEntries(Object.entries(patch).filter(([, value]) => value != null));
      if (previous) {
        queryClient.setQueryData<AlarmSnapshotRecord>(snapshotKey, {
          ...previous,
          definitions: previous.definitions.map(definition => (definition.id === Number(rule.id) ? { ...definition, ...changes } : definition)),
        });
      }
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(snapshotKey, context.previous);
    },
    onSettled: onSuccess,
  });
  const remove = useMutation({ mutationFn: (rule: Rule) => alarmsApi.remove(siteId, Number(rule.id)), onSuccess });
  return { create, update, remove };
}
