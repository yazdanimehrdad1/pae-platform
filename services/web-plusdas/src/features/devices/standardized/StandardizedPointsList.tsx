import { useMemo, useState } from "react";
import { Link2, Pencil, Unlink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { DevicePoint } from "@/api/types/devicePoints";
import { describeLink } from "./lib/pointLink";

/** A device's STANDARDIZED points and what each is linked to (a NATIVE point among `sources`).
 *  Unlinking asks for confirmation first; `onUnlink` runs only once it is confirmed. */
export function StandardizedPointsList({ points, sources, disabled, onLink, onUnlink }: {
  points: DevicePoint[];
  sources: DevicePoint[];
  disabled?: boolean;
  onLink: (point: DevicePoint) => void;
  onUnlink: (point: DevicePoint) => void;
}) {
  const sourcesById = useMemo(() => new Map(sources.map(source => [source.id, source])), [sources]);
  const [unlinking, setUnlinking] = useState<DevicePoint | null>(null);
  const unlinkingSource = unlinking?.source_point_id != null ? sourcesById.get(unlinking.source_point_id) : undefined;
  const unlinkingSourceName = unlinkingSource?.name ?? `point ${unlinking?.source_point_id}`;

  if (points.length === 0) {
    return <p className="py-3 text-sm text-muted-foreground">This device type has no standardized points.</p>;
  }

  return (
    <>
      <ul className="divide-y divide-border rounded-md border border-border">
        {points.map(point => {
          const link = describeLink(point, sourcesById);
          return (
            <li key={point.id} className="flex items-center gap-3 p-3" data-testid="standardized-point">
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{point.name}</span>
                  <Badge variant={link ? "secondary" : "outline"}>{link ? "linked" : "not linked"}</Badge>
                </div>
                <p className="truncate font-mono text-xs text-muted-foreground" title={link ?? undefined}>
                  {link ?? "No value until it is linked to a point on this device."}
                </p>
              </div>
              {link ? (
                <>
                  <Button variant="ghost" size="icon" className="h-8 w-8" disabled={disabled}
                    aria-label={`Edit link of ${point.name}`} onClick={() => onLink(point)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8" disabled={disabled}
                    aria-label={`Unlink ${point.name}`} onClick={() => setUnlinking(point)}>
                    <Unlink className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <Button variant="outline" size="sm" className="gap-1" disabled={disabled}
                  aria-label={`Link ${point.name}`} onClick={() => onLink(point)}>
                  <Link2 className="h-4 w-4" />Link
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      <AlertDialog open={unlinking !== null} onOpenChange={open => { if (!open) setUnlinking(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unlink {unlinking?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to unlink standardized point "{unlinking?.name}" from "{unlinkingSourceName}"?
              It will show no value until it is linked again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (unlinking) onUnlink(unlinking);
                setUnlinking(null);
              }}
            >
              Unlink
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
