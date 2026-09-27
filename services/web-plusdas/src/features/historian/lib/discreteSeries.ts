import { decodeEnum, isEnumPoint, parseSelectionId } from '@/shared/lib/discretePoints';
import type { CatalogPoint } from '../hooks/usePointCatalog';
import type { ChartRow } from '../types';

// A trended enum point or bitfield bit, with every state it can show, in plotting order.
// Both discrete renderers (state lanes, step lines) draw from this.
export interface DiscreteState {
  value: number;
  label: string;
}

export interface DiscreteSeries {
  key: string;
  kind: 'enum' | 'bit';
  name: string;
  color: string;
  states: DiscreteState[];
}

const BIT_STATES: DiscreteState[] = [{ value: 0, label: 'off' }, { value: 1, label: 'on' }];

// Returns null for an analog selection. Enum states are the labelled values in numeric order,
// plus any unlabelled value that actually occurs in `rows`.
export function describeDiscreteSeries(
  selectionId: string,
  pointsById: Map<string, CatalogPoint>,
  rows: ChartRow[],
  display: { name: string; color: string },
): DiscreteSeries | null {
  const { pointId, bit } = parseSelectionId(selectionId);
  const point = pointsById.get(pointId)?.point;
  if (!point) return null;

  if (bit !== undefined) return { key: selectionId, kind: 'bit', ...display, states: BIT_STATES };
  if (!isEnumPoint(point)) return null;

  const values = new Set(Object.keys(point.enum_detail ?? {}).map(Number).filter(Number.isFinite));
  for (const row of rows) if (row[selectionId] != null) values.add(Math.round(row[selectionId]));
  const states = [...values].sort((left, right) => left - right)
    .map(value => ({ value, label: decodeEnum(value, point.enum_detail) }));
  return { key: selectionId, kind: 'enum', ...display, states };
}

export function stateLabel(series: DiscreteSeries, rawValue: number): string {
  const value = Math.round(rawValue);
  return series.states.find(state => state.value === value)?.label ?? `Unknown (${value})`;
}
