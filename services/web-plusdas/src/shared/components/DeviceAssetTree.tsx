import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, ChevronDown, Folder, FolderOpen, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { devicesApi } from "@/api/devices";
import { POINT_GROUP_ORDER, type DevicePointsEntry, type PointGroup } from "@/api/types/devices";
import type { DevicePoint } from "@/api/types/devicePoints";
import { toast } from "@/shared/hooks/use-toast";
import { bitSelectionId, isBitfieldPoint, isEnumPoint, parseSelectionId, sortedBits } from "@/shared/lib/discretePoints";

const POINT_GROUP_LABELS: Record<PointGroup, string> = {
  standardized: "Standardized",
  virtual: "Virtual",
  native: "Native",
};

// Display name of a selection: "device-point", or "device-point · bit label" for one bit of a bitfield.
function resolveSelectionLabels(devices: DevicePointsEntry[], selectionIds: string[]): Record<string, string> {
  const pointsById = new Map<string, { point: DevicePoint; deviceName: string }>();
  devices.forEach(device => device.points.forEach(point => pointsById.set(String(point.id), { point, deviceName: device.deviceName })));
  const resolved: Record<string, string> = {};
  selectionIds.forEach(selectionId => {
    const { pointId, bit } = parseSelectionId(selectionId);
    const entry = pointsById.get(pointId);
    if (!entry) return;
    const pointLabel = `${entry.deviceName}-${entry.point.name}`;
    if (bit === undefined) { resolved[selectionId] = pointLabel; return; }
    const bitLabel = sortedBits(entry.point.bitfield_detail).find(definition => definition.bit === bit)?.label ?? `bit ${bit}`;
    resolved[selectionId] = `${pointLabel} · ${bitLabel}`;
  });
  return resolved;
}

function TypeBadge({ label }: { label: string }) {
  return <span className="ml-2 rounded border border-border px-1 text-[10px] uppercase tracking-wide text-muted-foreground">{label}</span>;
}

// The tree nodes to expand so a selection's row is visible: device, category folder, and for a
// bit, its bitfield point. Null when the point isn't on this site.
function nodePathTo(devices: DevicePointsEntry[], selectionId: string): string[] | null {
  const { pointId, bit } = parseSelectionId(selectionId);
  for (const device of devices) {
    const group = POINT_GROUP_ORDER.find(candidate => device.groups[candidate].some(point => String(point.id) === pointId));
    if (!group) continue;
    const path = [device.deviceName, `${device.deviceId}:${group}`];
    if (bit !== undefined) path.push(`point:${pointId}`);
    return path;
  }
  return null;
}

// Ask the tree to show one selection: expand down to it, scroll to it, highlight it briefly.
// A new `requestId` repeats the reveal for the same selection.
export interface RevealRequest {
  selectionId: string;
  requestId: number;
}

const REVEAL_HIGHLIGHT_MS = 2000;

export function DeviceAssetTree({ siteId, siteName, selectedPoints, onSelect, onResolveLabels, pointIdsToResolve, maxPoints = 5, expandBitfields = false, revealRequest }: {
  siteId: string | null;
  siteName: string;
  selectedPoints: string[];
  onSelect: (points: string[], labels: Record<string, string>) => void;
  onResolveLabels?: (labels: Record<string, string>) => void;
  pointIdsToResolve?: string[];
  maxPoints?: number;
  // List each labelled bit of a bitfield point as its own selectable row ("12:bit3").
  expandBitfields?: boolean;
  revealRequest?: RevealRequest | null;
}) {
  const [siteExpanded, setSiteExpanded] = useState(true);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [revealed, setRevealed] = useState<RevealRequest | null>(null);
  const treeRef = useRef<HTMLDivElement>(null);

  const { data: devices = [], isLoading, isError } = useQuery({
    queryKey: ['site-devices-with-points', siteId],
    queryFn: () => devicesApi.getBySiteWithPoints(siteId!),
    enabled: !!siteId,
  });

  useEffect(() => {
    if (!revealRequest || devices.length === 0) return;
    const path = nodePathTo(devices, revealRequest.selectionId);
    if (!path) return;
    setSiteExpanded(true);
    setExpandedNodes(prev => new Set([...prev, ...path]));
    setRevealed(revealRequest);
  }, [revealRequest, devices]);

  // Runs after the expanded rows have rendered.
  useEffect(() => {
    if (!revealed) return;
    const row = treeRef.current?.querySelector(`[data-selection-id="${revealed.selectionId}"]`);
    row?.scrollIntoView?.({ block: "center", behavior: "smooth" });
    const timer = setTimeout(() => setRevealed(null), REVEAL_HIGHLIGHT_MS);
    return () => clearTimeout(timer);
  }, [revealed]);

  const idsToResolveRef = useRef(pointIdsToResolve ?? selectedPoints);
  idsToResolveRef.current = pointIdsToResolve ?? selectedPoints;

  useEffect(() => {
    if (devices.length === 0) return;
    const resolved = resolveSelectionLabels(devices, idsToResolveRef.current);
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

  const warnLimit = () => toast({
    title: "Point limit reached",
    description: `A trend can hold up to ${maxPoints} points. Remove one to add another.`,
    variant: "destructive",
  });

  // Adds or removes a set of selections together (one point, or every bit of a bitfield).
  const toggleSelections = (selectionIds: string[]) => {
    const allSelected = selectionIds.every(id => selectedPoints.includes(id));
    if (allSelected) {
      onSelect(selectedPoints.filter(id => !selectionIds.includes(id)), {});
      return;
    }
    const toAdd = selectionIds.filter(id => !selectedPoints.includes(id));
    if (selectedPoints.length + toAdd.length > maxPoints) { warnLimit(); return; }
    onSelect([...selectedPoints, ...toAdd], resolveSelectionLabels(devices, toAdd));
  };

  // Every selectable row has the same layout: an expander slot (a chevron, or an empty spacer of the
  // same width), then the checkbox and the name, so points, enums and bitfields line up.
  const renderSelectableRow = (selectionId: string, label: string, indent: number, options: {
    badge?: string;
    hint?: string;
    expander?: { isExpanded: boolean; onToggle: () => void; label: string };
  } = {}) => {
    const isSelected = selectedPoints.includes(selectionId);
    const { badge, hint, expander } = options;
    return (
      <div
        key={selectionId}
        data-selection-id={selectionId}
        className={`flex items-center py-1 px-2 hover:bg-muted/50 rounded cursor-pointer transition-shadow ${isSelected ? 'bg-primary/5' : ''} ${revealed?.selectionId === selectionId ? 'ring-2 ring-primary' : ''}`}
        style={{ paddingLeft: `${indent}px` }}
        onClick={() => toggleSelections([selectionId])}
      >
        {expander ? (
          <button
            type="button"
            className="mr-1 flex h-4 w-4 shrink-0 items-center justify-center rounded hover:bg-muted"
            aria-label={expander.label}
            aria-expanded={expander.isExpanded}
            onClick={event => { event.stopPropagation(); expander.onToggle(); }}
          >
            {expander.isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        ) : (
          <span className="mr-1 h-4 w-4 shrink-0" aria-hidden />
        )}
        <div className="mr-3 pointer-events-none">
          <Checkbox checked={isSelected} onCheckedChange={() => {}} />
        </div>
        <span className="text-sm">{label}</span>
        {badge && <TypeBadge label={badge} />}
        {hint && <span className="ml-2 text-xs text-muted-foreground">{hint}</span>}
      </div>
    );
  };

  // The point's own checkbox trends its raw value; its chevron opens a subtree of its bits.
  const renderBitfieldPoint = (point: DevicePoint, indent: number) => {
    const bitNodeId = `point:${point.id}`;
    const isExpanded = expandedNodes.has(bitNodeId);
    const bits = sortedBits(point.bitfield_detail);
    const selectedBitCount = bits.filter(definition => selectedPoints.includes(bitSelectionId(point.id, definition.bit))).length;
    return (
      <div key={point.id}>
        {renderSelectableRow(String(point.id), point.name, indent, {
          badge: "bits",
          hint: !isExpanded && selectedBitCount > 0 ? `${selectedBitCount} bit${selectedBitCount > 1 ? 's' : ''} selected` : undefined,
          expander: { isExpanded, onToggle: () => toggleNode(bitNodeId), label: `Bits of ${point.name}` },
        })}
        {isExpanded && bits.map(definition =>
          renderSelectableRow(bitSelectionId(point.id, definition.bit), `${definition.bit} · ${definition.label}`, indent + 20),
        )}
      </div>
    );
  };

  const renderPoint = (point: DevicePoint, indent: number) => {
    if (expandBitfields && isBitfieldPoint(point)) return renderBitfieldPoint(point, indent);
    const badge = isEnumPoint(point) ? "enum" : isBitfieldPoint(point) ? "bits" : undefined;
    return renderSelectableRow(String(point.id), point.name, indent, { badge });
  };

  if (isLoading) return <div className="p-3 text-sm text-muted-foreground">Loading devices...</div>;
  if (isError) return <div className="p-3 text-sm text-destructive">Failed to load devices</div>;

  return (
    <div ref={treeRef} className="rounded-md border border-border bg-card overflow-auto">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-xs text-muted-foreground">{selectedPoints.length} / {maxPoints} selected</span>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1 px-2 text-xs"
          disabled={selectedPoints.length === 0}
          onClick={() => onSelect([], {})}
        >
          <X className="w-3 h-3" />Clear selection
        </Button>
      </div>
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

                {isDeviceExpanded && POINT_GROUP_ORDER.filter(group => device.groups[group].length > 0).map(group => {
                  const groupNodeId = `${device.deviceId}:${group}`;
                  const isGroupExpanded = expandedNodes.has(groupNodeId);
                  const groupPoints = device.groups[group];
                  return (
                    <div key={group} data-testid={`point-group-${group}`}>
                      <div
                        className="flex items-center py-1 px-2 hover:bg-muted/50 rounded cursor-pointer"
                        style={{ paddingLeft: '40px' }}
                        onClick={() => toggleNode(groupNodeId)}
                      >
                        {isGroupExpanded ? <ChevronDown className="w-4 h-4 mr-1" /> : <ChevronRight className="w-4 h-4 mr-1" />}
                        {isGroupExpanded ? <FolderOpen className="w-4 h-4 mr-2 text-muted-foreground" /> : <Folder className="w-4 h-4 mr-2 text-muted-foreground" />}
                        <span className="text-sm">{POINT_GROUP_LABELS[group]}</span>
                        <span className="ml-2 text-xs text-muted-foreground">({groupPoints.length})</span>
                      </div>

                      {isGroupExpanded && groupPoints.map(point => renderPoint(point, 60))}
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
