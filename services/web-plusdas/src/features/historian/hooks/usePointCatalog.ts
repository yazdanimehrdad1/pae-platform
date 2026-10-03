import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import type { DevicePoint } from '@/api/types/devicePoints';

export interface CatalogPoint {
  point: DevicePoint;
  deviceId: string;
}

// Every point of the site by id, from the cache the asset tree already fills (no extra request).
export function usePointCatalog(siteId: string | null): { pointsById: Map<string, CatalogPoint>; isLoading: boolean } {
  const { data: deviceEntries = [], isLoading } = useQuery({
    queryKey: ['site-devices-with-points', siteId],
    queryFn: () => devicesApi.getBySiteWithPoints(siteId!),
    enabled: !!siteId,
  });

  const pointsById = useMemo(() => {
    const catalog = new Map<string, CatalogPoint>();
    for (const device of deviceEntries) {
      for (const point of device.points) catalog.set(String(point.id), { point, deviceId: String(device.deviceId) });
    }
    return catalog;
  }, [deviceEntries]);

  return { pointsById, isLoading };
}
