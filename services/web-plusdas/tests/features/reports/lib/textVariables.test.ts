import { describe, expect, it } from 'vitest';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { ReportTextVariables } from '@/api/types/reports';
import type { ConditionPointOption } from '@/shared/components/conditions/conditionModel';
import { deviceToken, insertAt, pointToken, previewText, siteToken } from '@/features/reports/lib/textVariables';

const VARIABLES: ReportTextVariables = {
  site: [{ name: 'site_name', description: 'Site name' }, { name: 'window_start', description: 'Period start (site time)' }],
  device_fields: [{ name: 'name', description: 'Name' }, { name: 'type', description: 'Type' }, { name: 'vendor', description: 'Vendor' }],
  point_fields: [{ name: 'name', description: 'Name' }, { name: 'unit', description: 'Unit' }, { name: 'max', description: 'Maximum in the period' }],
};
const DEVICES = [{ deviceId: 12, deviceName: 'gen_1', deviceType: 'GENERATOR' }] as DevicePointsEntry[];
const POINTS = [{ id: '34', name: 'active_power', label: 'gen_1 · active_power', group: 'gen_1', kind: 'numeric', unit: 'kW' }] as ConditionPointOption[];
const context = { siteName: 'Alpha Solar Farm', variables: VARIABLES, devices: DEVICES, points: POINTS };

describe('tokens', () => {
  it("are written the way backend-ot reads them", () => {
    expect(siteToken('site_name')).toBe('{site_name}');
    expect(deviceToken(12, 'name')).toBe('{device:12.name}');
    expect(pointToken(34, 'max')).toBe('{point:34.max}');
  });
});

describe('insertAt', () => {
  it('replaces the selection and puts the caret after the token', () => {
    expect(insertAt('In the event  trips', '{device:12.name}', 13, 13)).toEqual({ body: 'In the event {device:12.name} trips', caret: 29 });
    expect(insertAt('abc XYZ', '{site_name}', 4, 7)).toEqual({ body: 'abc {site_name}', caret: 15 });
  });

  it('appends when the cursor is past the end', () => {
    expect(insertAt('abc', '{x}', 99, 99)).toEqual({ body: 'abc{x}', caret: 6 });
  });
});

describe('previewText', () => {
  it('fills in names and shows computed values as ‹what›', () => {
    const body = 'In the event {device:12.name} ({device:12.type}) explodes at {site_name}, {point:34.name} peaked at {point:34.max} {point:34.unit} after {window_start}.';
    expect(previewText(body, context)).toBe(
      'In the event gen_1 (GENERATOR) explodes at Alpha Solar Farm, active_power peaked at ‹max of active_power› kW after ‹period start (site time)›.',
    );
  });

  it('leaves what it cannot fill in as written', () => {
    expect(previewText('{device_name} {device:99.name} {point:99.max} {nope}', context)).toBe('{device_name} {device:99.name} {point:99.max} {nope}');
  });
});
