import { describe, expect, it } from 'vitest';
import {
  FALLBACK_COLORS, pruneSeriesStyles, resolveSeriesStyles, sanitizeSeriesStyles, toHexColor,
} from '@/features/historian/lib/seriesStyles';

describe('resolveSeriesStyles', () => {
  it('gives each line a distinct automatic colour, solid, 2 px by default', () => {
    const styles = resolveSeriesStyles(['7', '9']);
    expect(styles.get('7')).toEqual({ color: FALLBACK_COLORS[0], dash: 'solid', width: 2 });
    expect(styles.get('9')).toEqual({ color: FALLBACK_COLORS[1], dash: 'solid', width: 2 });
  });

  it('draws a PV forecast dashed by default', () => {
    expect(resolveSeriesStyles(['fc:site:pv_power']).get('fc:site:pv_power')?.dash).toBe('dashed');
  });

  it('uses the fields the user changed and the defaults for the rest', () => {
    const styles = resolveSeriesStyles(['7', '9'], { '9': { color: '#ff0000', dash: 'dotted' } });
    expect(styles.get('9')).toEqual({ color: '#ff0000', dash: 'dotted', width: 2 });
    expect(styles.get('7')?.dash).toBe('solid');
  });

  it('never gives an automatic line a colour the user picked', () => {
    const styles = resolveSeriesStyles(['7', '9'], { '9': { color: FALLBACK_COLORS[0].toLowerCase() } });
    expect(styles.get('7')?.color).toBe(FALLBACK_COLORS[1]);
  });
});

describe('sanitizeSeriesStyles', () => {
  it('keeps valid fields and drops the rest', () => {
    expect(sanitizeSeriesStyles({
      '7': { color: '#00ff00', dash: 'wavy', width: 9 },
      '9': { dash: 'dotted', width: 3 },
      '11': { color: 'red' },
    })).toEqual({ '7': { color: '#00ff00' }, '9': { dash: 'dotted', width: 3 } });
  });

  it('returns undefined for nothing valid', () => {
    expect(sanitizeSeriesStyles(undefined)).toBeUndefined();
    expect(sanitizeSeriesStyles(['#fff'])).toBeUndefined();
    expect(sanitizeSeriesStyles({ '7': { color: 'blue' } })).toBeUndefined();
  });
});

describe('pruneSeriesStyles', () => {
  it('drops the styles of points no longer on the trend', () => {
    expect(pruneSeriesStyles({ '7': { width: 1 }, '9': { width: 3 } }, ['9'])).toEqual({ '9': { width: 3 } });
    expect(pruneSeriesStyles({ '7': { width: 1 } }, [])).toBeUndefined();
  });
});

describe('toHexColor', () => {
  it('keeps hex and converts an automatic hsl colour', () => {
    expect(toHexColor('#3B82F6')).toBe('#3b82f6');
    expect(toHexColor('hsl(0, 100%, 50%)')).toBe('#ff0000');
    expect(toHexColor('hsl(120, 100%, 25%)')).toBe('#008000');
  });
});
