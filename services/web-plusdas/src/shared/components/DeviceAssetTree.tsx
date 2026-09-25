import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, ChevronDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { devicesApi } from "@/api/devices";

export function DeviceAssetTree({ siteId, siteName, selectedPoints, onSelect, onResolveLabels, pointIdsToResolve, maxPoints = 5 }: {
  siteId: string | null;
  siteName: string;
  selectedPoints: string[];
  onSelect: (points: string[], labels: Record<string, string>) => void;
  onResolveLabels?: (labels: Record<string, string>) => void;
  pointIdsToResolve?: string[];
  maxPoints?: number;
}) {
  const [siteExpanded, setSiteExpanded] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const { data: devices = [], isLoading, isError } = useQuery({
    queryKey: ['site-devices-with-points', siteId],
    queryFn: () => devicesApi.getBySiteWithPoints(siteId!),
    enabled: !!siteId,
  });

  const idsToResolveRef = useRef(pointIdsToResolve ?? selectedPoints);
  idsToResolveRef.current = pointIdsToResolve ?? selectedPoints;

  useEffect(() => {
    if (devices.length === 0) return;
    const idToName = new Map<string, string>();
    devices.forEach(device => device.points.forEach(p => idToName.set(String(p.id), p.name)));
    const resolved: Record<string, string> = {};
    idsToResolveRef.current.forEach(pointId => {
      const name = idToName.get(pointId);
      if (name) resolved[pointId] = name;
    });
    if (Object.keys(resolved).length > 0) onResolveLabels?.(resolved);
    // Depends only on `devices`: hydrate labels whenever the points catalog loads/changes,
    // not on every selection change (selection is read via a ref to avoid that loop).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [devices]);

  const toggleNode = (nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId); else next.add(nodeId);
      return next;
    });
  };

  const togglePoint = (pointId: string, pointName: string) => {
    const isSelected = selectedPoints.includes(pointId);
    if (!isSelected && selectedPoints.length >= maxPoints) return;
    const nextPoints = isSelected ? selectedPoints.filter(p => p !== pointId) : [...selectedPoints, pointId];
    onSelect(nextPoints, isSelected ? {} : { [pointId]: pointName });
  };

  if (isLoading) return <div className="p-3 text-sm text-muted-foreground">Loading devices...</div>;
  if (isError) return <div className="p-3 text-sm text-destructive">Failed to load devices</div>;

  return (
    <div className="rounded-md border border-border bg-card overflow-auto">
      <div className="p-3 space-y-1">
        <div className="select-none">
          <div
            className="flex items-center py-1 px-2 hover:bg-muted/50 rounded cursor-pointer"
            onClick={() => setSiteExpanded(prev => !prev)}
          >
            {siteExpanded ? <ChevronDown className="w-4 h-4 mr-1" /> : <ChevronRight className="w-4 h-4 mr-1" />}
            <span className="text-sm font-semibold">{siteName}</span>
          </div>

          {siteExpanded && devices.map(device => {
            const isDeviceExpanded = expandedNodes.has(device.deviceName);
            return (
              <div key={device.deviceId}>
                <div
                  className="flex items-center py-1 px-2 hover:bg-muted/50 rounded cursor-pointer bg-muted/30 font-medium"
                  style={{ paddingLeft: '24px' }}
                  onClick={() => toggleNode(device.deviceName)}
                >
                  {isDeviceExpanded ? <ChevronDown className="w-4 h-4 mr-1" /> : <ChevronRight className="w-4 h-4 mr-1" />}
                  <span className="text-sm">{device.deviceName}</span>
                </div>

                {isDeviceExpanded && device.points.map(point => {
                  const pointId = String(point.id);
                  const isSelected = selectedPoints.includes(pointId);
                  return (
                    <div
                      key={point.id}
                      className={`flex items-center py-1 px-2 hover:bg-muted/50 rounded cursor-pointer ${isSelected ? 'bg-primary/5' : ''}`}
                      style={{ paddingLeft: '40px' }}
                      onClick={() => togglePoint(pointId, point.name)}
                    >
                      <div className="mr-3 pointer-events-none">
                        <Checkbox checked={isSelected} onCheckedChange={() => {}} />
                      </div>
                      <span className="text-sm">{point.name}</span>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
