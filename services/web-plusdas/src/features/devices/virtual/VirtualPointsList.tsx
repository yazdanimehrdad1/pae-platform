import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { devicesApi } from "@/api/devices";
import type { DevicePoint } from "@/api/types/devicePoints";
import { toConditionPointOptions } from "./lib/pointOptions";
import { describeDraft, draftFromPoint } from "./lib/virtualDefinition";

/** A device's active virtual points, each with a plain-text summary of its definition. */
export function VirtualPointsList({ siteId, points, onEdit, onDelete }: {
  siteId: string;
  points: DevicePoint[];
  onEdit: (point: DevicePoint) => void;
  onDelete: (point: DevicePoint) => void;
}) {
  const { data: siteDevices = [] } = useQuery({
    queryKey: ["site-devices-with-points", siteId],
    queryFn: () => devicesApi.getBySiteWithPoints(siteId),
    enabled: points.length > 0 && !!siteId,
  });
  const pointsById = useMemo(
    () => new Map(toConditionPointOptions(siteDevices).map(option => [option.id, option])),
    [siteDevices],
  );

  if (points.length === 0) {
    return <p className="py-3 text-sm text-muted-foreground">No virtual points yet. Use "Add virtual point" to define one from other points on the site.</p>;
  }

  return (
    <ul className="divide-y divide-border rounded-md border border-border">
      {points.map(point => (
        <li key={point.id} className="flex items-start gap-3 p-3" data-testid="virtual-point">
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{point.name}</span>
              <Badge variant="outline">{point.virtual_definition?.kind ?? "no definition"}</Badge>
              {point.unit && <span className="text-xs text-muted-foreground">{point.unit}</span>}
            </div>
            {describeDraft(draftFromPoint(point), pointsById).map((line, index) => (
              <p key={index} className="truncate font-mono text-xs text-muted-foreground" title={line}>{line}</p>
            ))}
          </div>
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Edit ${point.name}`} onClick={() => onEdit(point)}>
            <Pencil className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`Delete ${point.name}`} onClick={() => onDelete(point)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </li>
      ))}
    </ul>
  );
}
