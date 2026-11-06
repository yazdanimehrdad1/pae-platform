import { describe, expect, it } from 'vitest';
import { fileName } from '@/shared/lib/download';

describe('fileName', () => {
  it('keeps lower-case words only', () => {
    expect(fileName('Daily Energy (Site 1)', 'hourly_stats')).toBe('daily-energy-site-1-hourly_stats');
  });
});
