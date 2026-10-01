import { describe, expect, it } from 'vitest';
import { buildAlarmModel, describeCondition, formatLimit, formatPointValue, ruleDeviceId } from './alarmModel';
import { testSnapshot } from './testData';

const snapshot = testSnapshot();
const model = buildAlarmModel(snapshot);
const rule = (name: string) => snapshot.rules.find(candidate => candidate.name === name)!;
const describe_ = (name: string) => describeCondition(rule(name), model.pointsById, model.devicesById);

describe('buildSnapshot (backend-ot records → page model)', () => {
  it('maps ids to strings and keeps every rule field', () => {
    expect(rule('bess_soc_low')).toMatchObject({
      id: '1', source: 'USER', kind: 'threshold', severity: 'fault', enabled: true, notify: { mobile: true, email: false },
    });
    expect(rule('pv_inverter_offline')).toMatchObject({ source: 'PROFILE', profileKey: 'inverter_offline', rule: null });
    expect(snapshot.now).toBe(Date.parse('2026-09-30T12:00:00Z'));
  });

  it("gives points their latest value and devices their newest native reading as last poll", () => {
    const soc = model.pointsById.get('64')!;
    expect([soc.value, soc.deviceId, soc.register, soc.label]).toEqual([15.5, '2', 64, 'bess-1 · state_of_charge']);
    expect(model.pointsById.get('166')).toMatchObject({ category: 'VIRTUAL', kind: 'enum', register: null, value: 1 });
    expect(model.pointsById.get('66')).toMatchObject({ kind: 'bitfield', value: null });
    expect(model.devicesById.get('2')!.lastPollAt).toBe('2026-09-30T11:59:45.000Z');
    expect(model.devicesById.get('3')!.lastPollAt).toBeNull();
  });
});

describe('buildAlarmModel', () => {
  it('lists active alarms faults first, and recently cleared ones', () => {
    expect(model.active.map(view => view.event.id)).toEqual(['101', '102']);
    expect(model.recentlyCleared.map(view => view.event.id)).toEqual(['103']);
    expect(model.active[0].point?.name).toBe('state_of_charge');
  });

  it('rates devices by their worst active alarm', () => {
    expect(model.deviceStatus.get('2')).toBe('fault');
    expect(model.deviceStatus.get('3')).toBe('warning');
    expect(model.sortedDevices.map(device => device.name)).toEqual(['bess-1', 'pv-1']);
  });
});

describe('describeCondition / formatLimit', () => {
  it('describes each kind with real point and device names', () => {
    expect(describe_('bess_soc_low')).toBe('bess-1 · state_of_charge < 20 % for 1 min');
    expect(describe_('pv_comms_lost')).toBe('pv-1: no successful poll > 60 s');
    expect(describe_('bess_trip_while_ready')).toBe('bess-1 · faults · trip is set and bess-1 · bess_ready is ready for 30 s');
    expect(describe_('pv_inverter_offline')).toBe('PV inverter is not producing');
  });

  it('formats the limit side', () => {
    expect(formatLimit(rule('bess_soc_low'), model.pointsById)).toBe('< 20 %');
    expect(formatLimit(rule('pv_comms_lost'), model.pointsById)).toBe('> 60 s');
    expect(formatLimit(rule('bess_trip_while_ready'), model.pointsById)).toBe('—');
  });

  it('finds the device a rule is about', () => {
    expect(ruleDeviceId(rule('bess_soc_low'), model.pointsById)).toBe('2');
    expect(ruleDeviceId(rule('pv_comms_lost'), model.pointsById)).toBe('3');
    expect(ruleDeviceId(rule('bess_trip_while_ready'), model.pointsById)).toBe('2');
    expect(ruleDeviceId(rule('pv_inverter_offline'), model.pointsById)).toBeNull();
  });

  it('formats values by point kind', () => {
    expect(formatPointValue(model.pointsById.get('64')!)).toBe('15.50 %');
    expect(formatPointValue(model.pointsById.get('166')!)).toBe('ready');
    expect(formatPointValue(model.pointsById.get('66')!, 9)).toBe('0x9');
    expect(formatPointValue(model.pointsById.get('66')!)).toBe('—');
  });
});
