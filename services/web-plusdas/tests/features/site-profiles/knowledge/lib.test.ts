import { describe, expect, it } from 'vitest';
import type { PointGuide } from '@/api/types/knowledge';
import type { ProfilePoint } from '@/api/types/siteProfiles';
import { itemStatus, linesToList, rowsToStates, stateRowsFor } from '@/features/site-profiles/knowledge/lib';

const STATUS: ProfilePoint = {
  name: 'INV1.State', device_id: 1, device_name: 'INV1', equipment: 'inverter', data_type: 'enum16',
  enum_labels: { 0: 'STOPPED', 1: 'RUNNING' },
};
const GUIDE: PointGuide = {
  site_id: 1, device_id: 1, point_name: 'State', meaning: 'Inverter state', updated_at: '2026-11-07T10:00:00Z', related_points: [], limits: [],
  states: [
    { kind: 'enum_value', code: 0, label: 'STOPPED', severity: 'fault', message: 'Inverter stopped', checks: ['Check the AC breaker'], probable_causes: [], related_points: [] },
    { kind: 'fault_code', code: 4410, label: 'GRID_FAULT', severity: 'fault', message: 'Grid fault', checks: [], probable_causes: [], related_points: [] },
  ],
};

describe('knowledge editing helpers', () => {
  it("lists backend-ot's states to fill, merged with the guide's entries, then its extra codes", () => {
    const rows = stateRowsFor(STATUS, GUIDE);
    expect(rows.map(row => [row.kind, row.code, row.label, row.message, row.fromCatalog])).toEqual([
      ['enum_value', 0, 'STOPPED', 'Inverter stopped', true],
      ['enum_value', 1, 'RUNNING', '', true],
      ['fault_code', 4410, 'GRID_FAULT', 'Grid fault', false],
    ]);
    expect(rows[0].checks).toBe('Check the AC breaker');
  });

  it('saves only the rows that have a message, with lists from lines', () => {
    const rows = stateRowsFor(STATUS, undefined);
    rows[1] = { ...rows[1], message: ' Running ', severity: 'info', checks: 'one\n\n two ' };
    expect(rowsToStates(rows)).toEqual([{
      kind: 'enum_value', code: 1, label: 'RUNNING', severity: 'info', message: 'Running', meaning: null,
      probable_causes: [], checks: ['one', 'two'], related_points: [], safety_note: null,
    }]);
    expect(linesToList(' a\n\nb ')).toEqual(['a', 'b']);
  });

  it("shows an item's draft status, else whether it is published", () => {
    const changes = [{ item_key: 'point:1:State', item_kind: 'point_guide' as const, kind: 'changed' as const, summary: '' }];
    expect(itemStatus('point:1:State', true, changes)).toBe('changed');
    expect(itemStatus('point:1:Other', true, changes)).toBe('published');
    expect(itemStatus('point:1:Other', false, changes)).toBe('none');
  });
});
