import type { DevicePoint } from '@/api/types/devicePoints';

// Enum and bitfield ("discrete") points: which points they are, how one bit of a bitfield is
// addressed as a selection, and how a stored raw value decodes to a label.
// Decoding assumes the stored value is the raw register integer (scale_factor 1), so it rounds first.

type PointDetail = Pick<DevicePoint, 'data_type' | 'enum_detail' | 'bitfield_detail'>;

const hasEntries = (detail: Record<string, string> | null | undefined) => !!detail && Object.keys(detail).length > 0;

export function isEnumPoint(point: PointDetail): boolean {
  return point.data_type.startsWith('enum') && hasEntries(point.enum_detail);
}

// status_word types carry bit labels the same way bitfields do.
export function isBitfieldPoint(point: PointDetail): boolean {
  return /^(bitfield|status_word)/.test(point.data_type) && hasEntries(point.bitfield_detail);
}

// One labelled bit of a bitfield, in bit order. Keys are bit indexes, optionally prefixed "bit-".
export interface BitDefinition {
  bit: number;
  label: string;
}

export function sortedBits(bitfieldDetail: Record<string, string> | null | undefined): BitDefinition[] {
  return Object.entries(bitfieldDetail ?? {})
    .map(([key, label]) => ({ bit: Number(key.replace(/^bit-/i, '')), label }))
    .filter(definition => Number.isInteger(definition.bit) && definition.bit >= 0)
    .sort((left, right) => left.bit - right.bit);
}

// A selection is a point id ("12") or one bit of a bitfield point ("12:bit3").
const BIT_SELECTION = /^(\d+):bit(\d+)$/;

export function bitSelectionId(pointId: string | number, bit: number): string {
  return `${pointId}:bit${bit}`;
}

export function parseSelectionId(selectionId: string): { pointId: string; bit?: number } {
  const match = BIT_SELECTION.exec(selectionId);
  return match ? { pointId: match[1], bit: Number(match[2]) } : { pointId: selectionId };
}

export function decodeBit(rawValue: number, bit: number): 0 | 1 {
  // BigInt keeps bits above 31 correct, where JS bitwise operators would wrap.
  return Number((BigInt(Math.round(rawValue)) >> BigInt(bit)) & 1n) as 0 | 1;
}

export function decodeEnum(rawValue: number, enumDetail: Record<string, string> | null | undefined): string {
  const value = Math.round(rawValue);
  return enumDetail?.[String(value)] ?? `Unknown (${value})`;
}
