import { describe, expect, it } from 'vitest';
import type { DevicePoint } from '@/api/types/devicePoints';
import {
  describeLink,
  draftFromPoint,
  powerScale,
  toLinkRequest,
  validateLinkDraft,
} from '@/features/devices/standardized/lib/pointLink';

const watts = { id: 14, name: 'W', category: 'NATIVE', unit: 'W' } as unknown as DevicePoint;
const linked = {
  id: 57, name: 'BESS_ACTIVE_POWER', category: 'STANDARDIZED', source_point_id: 14, unit: 'kW', scale_factor: 0.001,
} as unknown as DevicePoint;
const unlinked = { id: 58, name: 'BESS_STATUS', category: 'STANDARDIZED' } as unknown as DevicePoint;

describe('powerScale', () => {
  it('converts between power units, as backend-ot checks', () => {
    expect(powerScale('W', 'kW')).toBe(0.001);
    expect(powerScale('MW', 'kW')).toBe(1000);
    expect(powerScale('kW', 'kW')).toBe(1);
  });

  it('has no opinion on other quantities', () => {
    expect(powerScale('%', '%')).toBeNull();
    expect(powerScale('W', '')).toBeNull();
    expect(powerScale(null, 'kW')).toBeNull();
  });
});

describe('validateLinkDraft', () => {
  it('needs a source and a numeric scale', () => {
    expect(validateLinkDraft({ sourcePointId: '', unit: '', scale: 'x' }, null)).toEqual({
      source: 'Pick the point this one shows.', scale: 'Enter a number.',
    });
  });

  it('rejects a power scale that does not convert the units', () => {
    expect(validateLinkDraft({ sourcePointId: '14', unit: 'kW', scale: '1' }, 'W').scale)
      .toBe('W to kW needs a scale of 0.001.');
    expect(validateLinkDraft({ sourcePointId: '14', unit: 'kW', scale: '0.001' }, 'W')).toEqual({});
  });

  it('accepts any scale for other quantities', () => {
    expect(validateLinkDraft({ sourcePointId: '15', unit: '%', scale: '2' }, '%')).toEqual({});
  });
});

describe('draft and request', () => {
  it('round-trips a linked point', () => {
    const draft = draftFromPoint(linked);
    expect(draft).toEqual({ sourcePointId: '14', unit: 'kW', scale: '0.001' });
    expect(toLinkRequest(draft)).toEqual({ source_point_id: 14, unit: 'kW', scale_factor: 0.001 });
  });

  it('starts an unlinked point empty with scale 1, and sends a blank unit as null', () => {
    const draft = draftFromPoint(unlinked);
    expect(draft).toEqual({ sourcePointId: '', unit: '', scale: '1' });
    expect(toLinkRequest({ ...draft, sourcePointId: '14', unit: '  ' }).unit).toBeNull();
  });
});

describe('describeLink', () => {
  it('names the source, the scale and the unit', () => {
    expect(describeLink(linked, new Map([[14, watts]]))).toBe('W × 0.001 → kW');
    expect(describeLink({ ...linked, scale_factor: 1, unit: null }, new Map([[14, watts]]))).toBe('W');
  });

  it('falls back to the id when the source is not among the device points', () => {
    expect(describeLink(linked, new Map())).toBe('point 14 × 0.001 → kW');
  });

  it('is null for an unlinked point', () => {
    expect(describeLink(unlinked, new Map())).toBeNull();
  });
});
