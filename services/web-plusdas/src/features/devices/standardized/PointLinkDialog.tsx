import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { devicesApi } from "@/api/devices";
import { getErrorMessage } from "@/api/client";
import type { DevicePoint } from "@/api/types/devicePoints";
import { toast } from "@/shared/hooks/use-toast";
import { draftFromPoint, powerScale, toLinkRequest, validateLinkDraft, type PointLinkDraft } from "./lib/pointLink";

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? <p id={id} role="alert" className="text-xs text-alarm-fault">{message}</p> : null;
}

/** Link a STANDARDIZED point to one of its device's active NATIVE points (`sources`), or change its link. */
export function PointLinkDialog({ open, onOpenChange, siteId, deviceId, point, sources }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  deviceId: number;
  point: DevicePoint | null;
  sources: DevicePoint[];
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<PointLinkDraft>({ sourcePointId: "", unit: "", scale: "1" });
  const [hasTriedSave, setHasTriedSave] = useState(false);

  useEffect(() => {
    if (!open || !point) return;
    setDraft(draftFromPoint(point));
    setHasTriedSave(false);
  }, [open, point]);

  const source = sources.find(candidate => String(candidate.id) === draft.sourcePointId);
  const errors = validateLinkDraft(draft, source?.unit);
  const shownErrors = hasTriedSave ? errors : {};

  // Between power units the scale follows from the units, so fill it in as they change.
  const update = (changes: Partial<PointLinkDraft>) => {
    setDraft(previous => {
      const next = { ...previous, ...changes };
      const nextSource = sources.find(candidate => String(candidate.id) === next.sourcePointId);
      const expected = powerScale(nextSource?.unit, next.unit.trim());
      return expected !== null && !("scale" in changes) ? { ...next, scale: String(expected) } : next;
    });
  };

  const saveMutation = useMutation({
    mutationFn: () => devicesApi.linkPoint(siteId, deviceId, point!.id, toLinkRequest(draft)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["device-points", siteId, deviceId] });
      queryClient.invalidateQueries({ queryKey: ["device-record", siteId, deviceId] });
      toast({ title: `${point?.name} linked` });
      onOpenChange(false);
    },
    onError: (error) => toast({ title: "Failed to link point", description: getErrorMessage(error), variant: "destructive" }),
  });

  const handleSave = () => {
    setHasTriedSave(true);
    if (Object.keys(errors).length === 0) saveMutation.mutate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Link {point?.name}</DialogTitle>
          <DialogDescription>
            This standardized point will show the readings of a point on this device, multiplied by the scale.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="link-source">Source point</Label>
            <Select value={draft.sourcePointId} onValueChange={sourcePointId => update({ sourcePointId })}>
              <SelectTrigger id="link-source" aria-invalid={!!shownErrors.source} aria-describedby="link-source-error">
                <SelectValue placeholder={sources.length ? "Pick a point" : "This device has no points to link"} />
              </SelectTrigger>
              <SelectContent>
                {sources.map(candidate => (
                  <SelectItem key={candidate.id} value={String(candidate.id)}>
                    {candidate.name}{candidate.unit ? ` (${candidate.unit})` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FieldError id="link-source-error" message={shownErrors.source} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="link-unit">Unit</Label>
              <Input id="link-unit" value={draft.unit} maxLength={50} placeholder="e.g. kW"
                onChange={event => update({ unit: event.target.value })} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="link-scale">Scale (×)</Label>
              <Input id="link-scale" inputMode="decimal" value={draft.scale}
                onChange={event => update({ scale: event.target.value })}
                aria-invalid={!!shownErrors.scale} aria-describedby="link-scale-error" />
              <FieldError id="link-scale-error" message={shownErrors.scale} />
            </div>
          </div>
          {source && (
            <p className="rounded-md bg-muted/50 p-3 font-mono text-xs" aria-label="Summary">
              {point?.name} = {source.name}{source.unit ? ` [${source.unit}]` : ""} × {draft.scale || "?"}
              {draft.unit.trim() ? ` [${draft.unit.trim()}]` : ""}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleSave} disabled={saveMutation.isPending || !point}>
            {saveMutation.isPending ? "Saving..." : "Save link"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
