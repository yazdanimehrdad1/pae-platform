import { describe, expect, it } from 'vitest';
import { toStateSegments } from '@/features/historian/components/discrete/stateSegments';

describe('toStateSegments', () => {
  const rows = [
    { timestamp: 0, '1': 1 }, { timestamp: 10, '1': 1 }, { timestamp: 20, '1': 2 }, { timestamp: 30 }, { timestamp: 40, '1': 1 },
  ];

  it('merges equal neighbours and holds the last sample to the domain end', () => {
    expect(toStateSegments(rows, '1', [0, 50])).toEqual([
      { start: 0, end: 20, value: 1 }, { start: 20, end: 40, value: 2 }, { start: 40, end: 50, value: 1 },
    ]);
  });

  it('clips to a zoomed domain, keeping the state that started before it', () => {
    expect(toStateSegments(rows, '1', [15, 25])).toEqual([
      { start: 15, end: 20, value: 1 }, { start: 20, end: 25, value: 2 },
    ]);
  });
});
