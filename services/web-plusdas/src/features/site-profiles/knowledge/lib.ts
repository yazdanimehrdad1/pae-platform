import type {
  GuideSeverity, KnowledgeChange, KnowledgeKind, LimitCondition, PointGuide, StateGuide, StateKind,
} from '@/api/types/knowledge';
import type { ProfilePoint } from '@/api/types/siteProfiles';
import { statusOf } from '../lib/changes';

// Records, so a value added to intelli-gateway's contract fails the typecheck until it has a label.
export const SEVERITY_LABELS: Record<GuideSeverity, string> = { fault: 'Fault', warning: 'Warning', info: 'Info' };
export const STATE_KIND_LABELS: Record<StateKind, string> = { enum_value: 'State', bit: 'Bit', fault_code: 'Fault code' };
export const DOCUMENT_KIND_LABELS: Record<KnowledgeKind, string> = {
  manual: 'Manual', im_script: 'IM script', procedure: 'Procedure', experience_note: 'Experience note',
};
export const LIMIT_CONDITION_LABELS: Record<LimitCondition, string> = { above: 'Above', below: 'Below' };
export const SEVERITIES = Object.keys(SEVERITY_LABELS) as GuideSeverity[];
export const DOCUMENT_KINDS = Object.keys(DOCUMENT_KIND_LABELS) as KnowledgeKind[];

export const knowledgeQueryKey = (siteId: number) => ['site-profiles', siteId, 'knowledge'] as const;

export const guideKey = (deviceId: number, pointName: string) => `point:${deviceId}:${pointName}`;
export const documentKey = (documentId: string) => `document:${documentId}`;
export const factsKey = (deviceId: number) => `device:${deviceId}`;
export const promptKey = (promptId: string) => `prompt:${promptId}`;

/** True when the API answered 409: the draft moved since it was loaded. */
export const isDraftConflict = (error: unknown) => statusOf(error) === 409;

/** One editable row of a guide's states. Rows with an empty message aren't saved. */
export interface StateRow {
  kind: StateKind;
  code: number;
  label: string;
  severity: GuideSeverity;
  message: string;
  meaning: string;
  causes: string;
  checks: string;
  safetyNote: string;
  /** Prefilled from backend-ot's enum/bit labels (rather than added by hand). */
  fromCatalog: boolean;
}

export function linesToList(text: string): string[] {
  return text.split('\n').map(line => line.trim()).filter(Boolean);
}

export const listToLines = (items: readonly string[] | undefined) => (items ?? []).join('\n');

function rowFrom(state: StateGuide, fromCatalog: boolean): StateRow {
  return {
    kind: state.kind,
    code: state.code,
    label: state.label,
    severity: state.severity,
    message: state.message,
    meaning: state.meaning ?? '',
    causes: listToLines(state.probable_causes),
    checks: listToLines(state.checks),
    safetyNote: state.safety_note ?? '',
    fromCatalog,
  };
}

/**
 * The rows to edit: one per enum value or bit backend-ot labels (so nothing has to be typed twice),
 * filled from the existing guide where it has an entry, then the guide's other entries (e.g.
 * vendor fault codes) after them.
 */
export function stateRowsFor(point: ProfilePoint, guide: PointGuide | undefined): StateRow[] {
  const existing = new Map((guide?.states ?? []).map(state => [`${state.kind}:${state.code}`, state]));
  const catalog: { kind: StateKind; code: number; label: string }[] = [
    ...Object.entries(point.enum_labels ?? {}).map(([code, label]) => ({ kind: 'enum_value' as const, code: Number(code), label })),
    ...Object.entries(point.bit_labels ?? {}).map(([code, label]) => ({ kind: 'bit' as const, code: Number(code), label })),
  ];
  const rows = catalog.map(({ kind, code, label }) => {
    const known = existing.get(`${kind}:${code}`);
    existing.delete(`${kind}:${code}`);
    return known
      ? rowFrom(known, true)
      : { kind, code, label, severity: 'info' as const, message: '', meaning: '', causes: '', checks: '', safetyNote: '', fromCatalog: true };
  });
  return [...rows, ...[...existing.values()].map(state => rowFrom(state, false))];
}

/** The rows that were filled in (a message), as the API's states. */
export function rowsToStates(rows: StateRow[]): StateGuide[] {
  return rows
    .filter(row => row.message.trim() !== '')
    .map(row => ({
      kind: row.kind,
      code: row.code,
      label: row.label.trim() || String(row.code),
      severity: row.severity,
      message: row.message.trim(),
      meaning: row.meaning.trim() || null,
      probable_causes: linesToList(row.causes),
      checks: linesToList(row.checks),
      related_points: [],
      safety_note: row.safetyNote.trim() || null,
    }));
}

export type ItemStatus = 'published' | 'added' | 'changed' | 'removed' | 'none';

/** An item's state for the badge: what the draft does to it, else whether it is published. */
export function itemStatus(itemKey: string, exists: boolean, changes: KnowledgeChange[]): ItemStatus {
  const change = changes.find(entry => entry.item_key === itemKey);
  if (change) return change.kind;
  return exists ? 'published' : 'none';
}

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  published: 'Published', added: 'Draft: new', changed: 'Draft: changed', removed: 'Draft: removed', none: 'No guide',
};
