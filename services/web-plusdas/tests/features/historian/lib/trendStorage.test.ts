// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { loadTrendsFromStorage, saveTrendsToStorage } from '@/features/historian/lib/trendStorage';

afterEach(() => window.localStorage.clear());

describe('trend storage and the axis scale', () => {
  it('saves and loads a trend with its scale', () => {
    saveTrendsToStorage('user-1', [{ id: 't1', name: 'Mixed', points: ['7', '9'], scale: 'per-point' }]);
    expect(loadTrendsFromStorage('user-1')).toEqual([{ id: 't1', name: 'Mixed', points: ['7', '9'], scale: 'per-point' }]);
  });

  it('loads a trend saved before scales existed without one (it shows per unit)', () => {
    window.localStorage.setItem('historian_trends_user-1', JSON.stringify([{ id: 't1', name: 'Old', points: ['7'] }]));
    expect(loadTrendsFromStorage('user-1')).toEqual([{ id: 't1', name: 'Old', points: ['7'] }]);
  });

  it('saves and loads the signal styles', () => {
    const trend = { id: 't1', name: 'Styled', points: ['7', '9'], styles: { '7': { color: '#0000ff' }, '9': { color: '#ff0000', dash: 'dotted' as const, width: 3 as const } } };
    saveTrendsToStorage('user-1', [trend]);
    expect(loadTrendsFromStorage('user-1')).toEqual([trend]);
  });

  it('drops invalid styles', () => {
    window.localStorage.setItem('historian_trends_user-1', JSON.stringify([{ id: 't1', name: 'Odd', points: ['7'], styles: { '7': { color: 'blue', dash: 'wavy' } } }]));
    expect(loadTrendsFromStorage('user-1')).toEqual([{ id: 't1', name: 'Odd', points: ['7'] }]);
  });

  it('drops a scale it does not know', () => {
    window.localStorage.setItem('historian_trends_user-1', JSON.stringify([{ id: 't1', name: 'Odd', points: [], scale: 'log' }]));
    expect(loadTrendsFromStorage('user-1')[0].scale).toBeUndefined();
  });
});
