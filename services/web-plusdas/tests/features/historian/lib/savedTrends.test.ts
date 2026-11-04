import { describe, expect, it } from 'vitest';
import type { SavedTrend } from '@/api/types/me';
import { fromSavedTrend, parseLegacyTrends, sameDefinition, toDefinition } from '@/features/historian/lib/savedTrends';

const saved = (overrides: Partial<SavedTrend> = {}): SavedTrend => ({
  id: 7, position: 0, name: 'Mixed', points: ['7', '9'], scale: 'per-point', styles: null,
  created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z', ...overrides,
});

describe('a trend saved for the user', () => {
  it('becomes the UI trend, its id a string', () => {
    expect(fromSavedTrend(saved())).toEqual({ id: '7', name: 'Mixed', points: ['7', '9'], scale: 'per-point' });
  });

  it('keeps its styles and drops invalid ones (those lines get their default look)', () => {
    const trend = fromSavedTrend(saved({ styles: { '7': { color: '#0000ff' }, '9': { color: 'not a colour', dash: 'dotted', width: 3 } } }));
    expect(trend.styles).toEqual({ '7': { color: '#0000ff' }, '9': { dash: 'dotted', width: 3 } });
  });

  it('has no scale when none was saved (it shows per unit)', () => {
    expect(fromSavedTrend(saved({ scale: null })).scale).toBeUndefined();
  });

  it('round-trips to the definition the server stores', () => {
    const trend = fromSavedTrend(saved({ styles: { '7': { color: '#0000ff' } } }));
    expect(toDefinition(trend)).toEqual({ name: 'Mixed', points: ['7', '9'], scale: 'per-point', styles: { '7': { color: '#0000ff' } } });
    expect(toDefinition({ id: '1', name: 'Plain', points: [] })).toEqual({ name: 'Plain', points: [], scale: null, styles: null });
  });

  it('compares definitions, not ids', () => {
    const trend = fromSavedTrend(saved());
    expect(sameDefinition(trend, { ...trend, id: 'other' })).toBe(true);
    expect(sameDefinition(trend, { ...trend, points: ['7'] })).toBe(false);
    expect(sameDefinition(trend, { ...trend, styles: { '7': { width: 1 } } })).toBe(false);
  });
});

describe('trends saved in this browser before accounts', () => {
  it('reads the valid ones, dropping an unknown scale', () => {
    const stored = JSON.stringify([
      { id: 't1', name: 'Old', points: ['7'] },
      { id: 't2', name: 'Scaled', points: ['8'], scale: 'log' },
      { id: 't3', name: '', points: [] },
      'junk',
    ]);
    expect(parseLegacyTrends(stored)).toEqual([
      { id: 't1', name: 'Old', points: ['7'] },
      { id: 't2', name: 'Scaled', points: ['8'] },
    ]);
  });

  it('is nothing for missing or broken storage', () => {
    expect(parseLegacyTrends(null)).toEqual([]);
    expect(parseLegacyTrends('{not json')).toEqual([]);
    expect(parseLegacyTrends('{"name":"not a list"}')).toEqual([]);
  });
});
