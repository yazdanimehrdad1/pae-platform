// System alarms mock: the site from the alarms spec (8 devices polled over Modbus TCP/RTU), their
// points and the alarm rules. Values over time come from ./signals.ts.
import type { Device, Point, Rule } from '@/features/alarms/types';
import type { SiteInfo } from '@/features/alarms/data/AlarmDataSource';

export const MOCK_SITE: SiteInfo = { name: 'North substation', timeZone: 'America/Denver' };

type DeviceDef = Omit<Device, 'lastPollAt'>;

export const MOCK_DEVICES: DeviceDef[] = [
  { id: 't1', name: 'Transformer T1', type: 'transformer', protocol: 'modbus_tcp', address: '10.0.4.11', unitId: 1 },
  { id: 't2', name: 'Transformer T2', type: 'transformer', protocol: 'modbus_tcp', address: '10.0.4.12', unitId: 1 },
  { id: 'g1', name: 'Generator G1', type: 'generator', protocol: 'modbus_tcp', address: '10.0.4.21', unitId: 2 },
  { id: 'f1', name: 'Feeder F1', type: 'feeder', protocol: 'modbus_tcp', address: '10.0.4.22', unitId: 3 },
  { id: 'p1', name: 'Protection P1', type: 'protection', protocol: 'modbus_rtu', address: '/dev/ttyS1', unitId: 5 },
  { id: 'p2', name: 'Protection P2', type: 'protection', protocol: 'modbus_rtu', address: '/dev/ttyS1', unitId: 6 },
  { id: 's1', name: 'Switch S1', type: 'switch', protocol: 'modbus_rtu', address: '/dev/ttyS2', unitId: 7 },
  { id: 's2', name: 'Switch S2', type: 'switch', protocol: 'modbus_rtu', address: '/dev/ttyS2', unitId: 8 },
];

type PointDef = Omit<Point, 'value' | 'quality' | 'updatedAt'>;

const BREAKER_STATES = { 0: 'open', 1: 'closed' };

export const MOCK_POINTS: PointDef[] = [
  { id: 't1.top_oil_temp', deviceId: 't1', register: 30001, name: 'Top-oil temperature', unit: '°C', kind: 'numeric' },
  { id: 't1.winding_temp', deviceId: 't1', register: 30002, name: 'Winding temperature', unit: '°C', kind: 'numeric' },
  { id: 't1.load', deviceId: 't1', register: 30010, name: 'Load', unit: '%', kind: 'numeric' },
  { id: 't2.top_oil_temp', deviceId: 't2', register: 30001, name: 'Top-oil temperature', unit: '°C', kind: 'numeric' },
  { id: 't2.winding_temp', deviceId: 't2', register: 30002, name: 'Winding temperature', unit: '°C', kind: 'numeric' },
  { id: 't2.load', deviceId: 't2', register: 30010, name: 'Load', unit: '%', kind: 'numeric' },
  { id: 'g1.active_power', deviceId: 'g1', register: 30101, name: 'Active power', unit: 'MW', kind: 'numeric' },
  { id: 'g1.frequency', deviceId: 'g1', register: 30102, name: 'Frequency', unit: 'Hz', kind: 'numeric' },
  { id: 'g1.breaker', deviceId: 'g1', register: 10001, name: 'Breaker', unit: '', kind: 'discrete', states: BREAKER_STATES },
  { id: 'f1.load', deviceId: 'f1', register: 30201, name: 'Load (of rating)', unit: '%', kind: 'numeric' },
  { id: 'f1.current', deviceId: 'f1', register: 30202, name: 'Current', unit: 'A', kind: 'numeric' },
  { id: 'f1.breaker', deviceId: 'f1', register: 10001, name: 'Breaker', unit: '', kind: 'discrete', states: BREAKER_STATES },
  { id: 'p1.current_a', deviceId: 'p1', register: 30301, name: 'Phase A current', unit: 'A', kind: 'numeric' },
  { id: 'p1.current_b', deviceId: 'p1', register: 30302, name: 'Phase B current', unit: 'A', kind: 'numeric' },
  { id: 'p1.current_c', deviceId: 'p1', register: 30303, name: 'Phase C current', unit: 'A', kind: 'numeric' },
  { id: 'p2.current_a', deviceId: 'p2', register: 30301, name: 'Phase A current', unit: 'A', kind: 'numeric' },
  { id: 'p2.current_b', deviceId: 'p2', register: 30302, name: 'Phase B current', unit: 'A', kind: 'numeric' },
  { id: 'p2.current_c', deviceId: 'p2', register: 30303, name: 'Phase C current', unit: 'A', kind: 'numeric' },
  { id: 'p2.trip', deviceId: 'p2', register: 10001, name: 'Trip output', unit: '', kind: 'discrete', states: { 0: 'normal', 1: 'tripped' } },
  { id: 's1.position', deviceId: 's1', register: 10001, name: 'Position', unit: '', kind: 'discrete', states: BREAKER_STATES },
  { id: 's1.position_mismatch', deviceId: 's1', register: 10002, name: 'Position mismatch', unit: '', kind: 'discrete', states: { 0: 'no', 1: 'yes' } },
  { id: 's2.position', deviceId: 's2', register: 10001, name: 'Position', unit: '', kind: 'discrete', states: BREAKER_STATES },
  { id: 'site.import', deviceId: null, register: null, name: 'Site import', unit: 'MW', kind: 'numeric' },
];

const commsStale = (deviceId: string, name: string): Rule => ({
  id: `${deviceId}.comms_stale`, type: 'comms_stale', name: `${deviceId}_comms_lost`, deviceId,
  staleAfterSec: 60, severity: 'warning', message: `${name}: no successful poll for over 60 s`, enabled: true, notify: { mobile: false, email: false },
});

export const MOCK_RULES: Rule[] = [
  {
    id: 'p2.current_b.high', type: 'threshold', name: 'p2_phase_b_overcurrent', pointId: 'p2.current_b',
    operator: '>', threshold: 600, delaySec: 0, deadband: 20, severity: 'fault',
    message: 'Protection P2 phase B current above 600 A', enabled: true, notify: { mobile: true, email: true },
  },
  {
    id: 't1.top_oil_temp.high', type: 'threshold', name: 't1_top_oil_temp_high', pointId: 't1.top_oil_temp',
    operator: '>', threshold: 85, delaySec: 300, deadband: 2, severity: 'warning',
    message: 'Transformer T1 top-oil temperature above 85 °C for 5 min', enabled: true, notify: { mobile: true, email: false },
  },
  {
    id: 'site.import.high', type: 'threshold', name: 'site_import_high', pointId: 'site.import',
    operator: '>', threshold: 4.5, delaySec: 900, deadband: 0.1, severity: 'warning',
    message: 'Site import above 4.5 MW for 15 min', enabled: true, notify: { mobile: true, email: false },
  },
  {
    id: 'f1.load.high', type: 'threshold', name: 'f1_load_high', pointId: 'f1.load',
    operator: '>', threshold: 90, delaySec: 0, deadband: 2, severity: 'warning',
    message: 'Feeder F1 load above 90 % of rating', enabled: true, notify: { mobile: false, email: false },
  },
  {
    id: 's1.position_mismatch', type: 'threshold', name: 's1_position_mismatch', pointId: 's1.position_mismatch',
    operator: '=', threshold: 1, delaySec: 0, deadband: 0, severity: 'warning',
    message: 'Switch S1 position mismatch', enabled: true, notify: { mobile: true, email: false },
  },
  {
    id: 'g1.frequency.low', type: 'threshold', name: 'g1_underfrequency', pointId: 'g1.frequency',
    operator: '<', threshold: 59.5, delaySec: 30, deadband: 0.1, severity: 'fault',
    message: 'Generator G1 frequency below 59.5 Hz', enabled: true, notify: { mobile: true, email: false },
  },
  ...MOCK_DEVICES.map(device => commsStale(device.id, device.name)),
];

