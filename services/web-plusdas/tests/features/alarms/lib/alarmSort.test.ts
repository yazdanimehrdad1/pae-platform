import { describe, expect, it } from 'vitest';
import type { AlarmEvent } from '@/features/alarms/types';
import { compareActiveAlarms } from '@/features/alarms/lib/alarmSort';

const event = (id: string, severity: AlarmEvent['severity'], raisedAt: string): AlarmEvent => ({
  id, ruleId: 'r', deviceId: null, severity, raisedAt, clearedAt: null, valueAtRaise: 1, message: '',
});

describe('compareActiveAlarms', () => {
  it('orders HIGH before MEDIUM before LOW, then longest active first', () => {
    const events = [
      event('low-old', 'LOW', '2026-09-27T06:00:00Z'),
      event('medium-new', 'MEDIUM', '2026-09-27T09:30:00Z'),
      event('high-new', 'HIGH', '2026-09-27T09:50:00Z'),
      event('medium-old', 'MEDIUM', '2026-09-27T07:00:00Z'),
      event('high-old', 'HIGH', '2026-09-27T09:00:00Z'),
    ];
    expect([...events].sort(compareActiveAlarms).map(e => e.id)).toEqual([
      'high-old', 'high-new', 'medium-old', 'medium-new', 'low-old',
    ]);
  });
});
