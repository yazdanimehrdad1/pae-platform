import type { DevicePoint, StandardizedPointLinkRequest } from "@/api/types/devicePoints";

/** Power units backend-ot checks a link's scale between (the same table as its POWER_UNIT_TO_KW). */
const POWER_UNIT_TO_KW: Record<string, number> = { W: 0.001, kW: 1, MW: 1000 };

/** The form of a standardized point's link, as typed. */
export interface PointLinkDraft {
  sourcePointId: string;
  unit: string;
  scale: string;
}

export interface PointLinkErrors {
  source?: string;
  scale?: string;
}

export function draftFromPoint(point: DevicePoint): PointLinkDraft {
  return {
    sourcePointId: point.source_point_id != null ? String(point.source_point_id) : "",
    unit: point.unit ?? "",
    scale: String(point.scale_factor ?? 1),
  };
}

/** The scale that turns one power unit into another (W -> kW: 0.001), or null if either isn't one. */
export function powerScale(sourceUnit: string | null | undefined, unit: string | null | undefined): number | null {
  if (!sourceUnit || !unit || !(sourceUnit in POWER_UNIT_TO_KW) || !(unit in POWER_UNIT_TO_KW)) return null;
  return POWER_UNIT_TO_KW[sourceUnit] / POWER_UNIT_TO_KW[unit];
}

/** What's wrong with the draft before it is sent (backend-ot checks the same, and has the last word). */
export function validateLinkDraft(draft: PointLinkDraft, sourceUnit: string | null | undefined): PointLinkErrors {
  const errors: PointLinkErrors = {};
  if (!draft.sourcePointId) errors.source = "Pick the point this one shows.";
  const scale = Number(draft.scale);
  if (draft.scale.trim() === "" || !Number.isFinite(scale)) {
    errors.scale = "Enter a number.";
  } else {
    const expected = powerScale(sourceUnit, draft.unit.trim());
    if (expected !== null && Math.abs(scale - expected) > 1e-9 * Math.max(1, Math.abs(expected))) {
      errors.scale = `${sourceUnit} to ${draft.unit.trim()} needs a scale of ${expected}.`;
    }
  }
  return errors;
}

export function toLinkRequest(draft: PointLinkDraft): StandardizedPointLinkRequest {
  return {
    source_point_id: Number(draft.sourcePointId),
    unit: draft.unit.trim() || null,
    scale_factor: Number(draft.scale),
  };
}

/** One line describing a point's link, e.g. "W × 0.001 → kW", or null when it isn't linked. */
export function describeLink(point: DevicePoint, sourcesById: Map<number, DevicePoint>): string | null {
  if (point.source_point_id == null) return null;
  const source = sourcesById.get(point.source_point_id);
  const sourceName = source ? source.name : `point ${point.source_point_id}`;
  const scale = point.scale_factor ?? 1;
  const scaled = scale === 1 ? sourceName : `${sourceName} × ${scale}`;
  return point.unit ? `${scaled} → ${point.unit}` : scaled;
}
