import { describe, expect, it } from 'vitest';
import type { ProfileChange, ProfilePoint } from '@/api/types/siteProfiles';
import {
  approvalProblem, groupByTarget, labelsText, localPointName, statusOf,
} from '@/features/site-profiles/lib/changes';

const change = (change_id: string, target: ProfileChange['target']): ProfileChange => ({
  change_id, target, kind: 'added', summary: change_id, fields: [],
});

const point = (overrides: Partial<ProfilePoint> = {}): ProfilePoint => ({
  name: 'INV1.state', device_id: 1, device_name: 'INV1', equipment: 'inverter', data_type: 'enum16', ...overrides,
});

describe('site profile change helpers', () => {
  it('groups changes in a fixed order: site, devices, points, topology', () => {
    const groups = groupByTarget([change('topology', 'topology'), change('point:1:x', 'point'), change('site', 'site')]);
    expect(groups.map(group => group.target)).toEqual(['site', 'point', 'topology']);
  });

  it("refuses an empty selection, and a new site's first approval without the site", () => {
    expect(approvalProblem(new Set(), true)).toMatch(/Select/);
    expect(approvalProblem(new Set(['device:1']), false)).toMatch(/site itself/);
    expect(approvalProblem(new Set(['site', 'device:1']), false)).toBeNull();
    expect(approvalProblem(new Set(['device:1']), true)).toBeNull();
  });

  it('shows enum and bit labels on one line', () => {
    expect(labelsText(point({ enum_labels: { 0: 'off', 1: 'on' } }))).toBe('0 off · 1 on');
    expect(labelsText(point({ bit_labels: { 3: 'OVER_TEMP' } }))).toBe('bit 3 OVER_TEMP');
    expect(labelsText(point())).toBe('');
  });

  it("names a point within its device, and reads an error's status", () => {
    expect(localPointName(point())).toBe('state');
    expect(statusOf({ status: 404, detail: 'x' })).toBe(404);
    expect(statusOf(new Error('x'))).toBeUndefined();
  });
});
