import { describe, expect, it } from 'vitest';
import type { AlarmEvent } from '@/features/alarms/types';
import { compareActiveAlarms } from '@/features/alarms/lib/alarmSort';

const event = (id: string, severity: AlarmEvent['severity'], raisedAt: string): AlarmEvent => ({
  id, ruleId: 'r', deviceId: null, severity, raisedAt, clearedAt: null, valueAtRaise: 1, message: '',
});

describe('compareActiveAlarms', () => {
  it('orders faults before warnings, then longest active first', () => {
    const events = [
      event('warning-new', 'warning', '2026-09-27T09:30:00Z'),
      event('fault-new', 'fault', '2026-09-27T09:50:00Z'),
      event('warning-old', 'warning', '2026-09-27T07:00:00Z'),
      event('fault-old', 'fault', '2026-09-27T09:00:00Z'),
    ];
    expect([...events].sort(compareActiveAlarms).map(e => e.id)).toEqual([
      'fault-old', 'fault-new', 'warning-old', 'warning-new',
    ]);
  });
});
