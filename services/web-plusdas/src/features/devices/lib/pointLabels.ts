import type { DevicePointDataType } from '@/api/types/devicePoints';

// A point's value labels as one editable grid cell: "0=OFF; 3=RUNNING; 4=THROTTLED".
// For an enum16/32 point they are its enum_detail (code -> label); for a bitfield16/32 point its
// bitfield_detail (bit number -> label). Other data types carry none (backend-ot only applies
// labels to these four types). Pure: no React.

export type LabelKind = 'enum' | 'bitfield';
export type Labels = Record<string, string>;

const SEPARATOR = '; ';

/** Which detail a data type uses, or null when it takes no labels. */
export function labelKind(dataType: string): LabelKind | null {
  if (dataType === 'enum16' || dataType === 'enum32') return 'enum';
  if (dataType === 'bitfield16' || dataType === 'bitfield32') return 'bitfield';
  return null;
}

/** Largest code (enum) or bit number (bitfield) the type can hold. */
export function maxKey(dataType: DevicePointDataType | string): number {
  const wide = dataType.endsWith('32');
  if (labelKind(dataType) === 'bitfield') return wide ? 31 : 15;
  return wide ? 0xffff_ffff : 0xffff;
}

/** Labels as cell text, in numeric order of their codes/bits. */
export function formatLabels(labels: Labels | null | undefined): string {
  if (!labels) return '';
  return Object.entries(labels)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([key, label]) => `${key}=${label}`)
    .join(SEPARATOR);
}

export type ParseResult = { labels: Labels | null; error: null } | { labels: null; error: string };

/** Cell text -> labels (null when empty). "code=label" pairs separated by ";" (or new lines). */
export function parseLabels(text: string, dataType: string): ParseResult {
  const pairs = text.split(/[;\n]/).map((pair) => pair.trim()).filter((pair) => pair !== '');
  if (pairs.length === 0) return { labels: null, error: null };
  const kind = labelKind(dataType);
  if (kind === null) return { labels: null, error: `${dataType || 'this data type'} takes no labels (only enum and bitfield types do)` };
  const unit = kind === 'bitfield' ? 'bit' : 'code';
  const limit = maxKey(dataType);
  const labels: Labels = {};
  for (const pair of pairs) {
    const at = pair.indexOf('=');
    if (at < 1) return { labels: null, error: `"${pair}": write ${unit}=label` };
    const key = pair.slice(0, at).trim();
    const label = pair.slice(at + 1).trim();
    if (!/^\d+$/.test(key) || Number(key) > limit) {
      return { labels: null, error: `"${key}" isn't a ${unit} of ${dataType} (0–${limit})` };
    }
    if (label === '') return { labels: null, error: `${unit} ${key} has no label` };
    const normalized = String(Number(key));
    if (normalized in labels) return { labels: null, error: `${unit} ${normalized} appears twice` };
    labels[normalized] = label;
  }
  return { labels, error: null };
}

/** The update/create fields for a point's labels (the other detail is cleared). */
export function labelFields(labels: Labels | null, dataType: string): { enum_detail: Labels | null; bitfield_detail: Labels | null } {
  const kind = labelKind(dataType);
  return {
    enum_detail: kind === 'enum' ? labels : null,
    bitfield_detail: kind === 'bitfield' ? labels : null,
  };
}
