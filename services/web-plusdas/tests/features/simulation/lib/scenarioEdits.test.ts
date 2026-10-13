import { describe, expect, it } from 'vitest';
import type { EventScenario, FaultCauseInfo } from '@/api/types/powerflow';
import {
  blankExpectedRow,
  blankRow,
  causesFor,
  describeChange,
  describeExpectation,
  expectedPointFrom,
  expectedRowFrom,
  expectedRowProblems,
  rowFromEvent,
  rowProblems,
  scenarioFromRows,
  targetsFor,
} from '@/features/simulation/lib/scenarioEdits';
import { REFERENCE_SITE } from '../fixtures';

const SCENARIO: EventScenario = {
  schema_version: 1,
  description: 'Trip, sag, restore',
  events: [
    { at: { kind: 'step', step: 10 }, change: { type: 'asset_fault', asset_id: 'pv1', active: true, cause: 'ground_fault', auto_restore: false }, label: 'trip' },
    { at: { kind: 'sim_time', sim_time: '2026-06-21T12:00:00.000Z' }, change: { type: 'grid_voltage', vm_pu: 0.9 }, label: null },
    { at: { kind: 'step', step: 30 }, change: { type: 'comm_loss', target: 'poi_meter', id: null, active: false }, label: null },
    { at: { kind: 'step', step: 40 }, change: { type: 'breaker', breaker: 'poi', closed: false }, label: null },
    { at: { kind: 'step', step: 50 }, change: { type: 'grid_frequency', hz: null }, label: null },
    {
      at: { kind: 'step', step: 60 },
      change: { type: 'asset_fault', asset_id: 'bess1', active: true, cause: 'trip', auto_restore: true },
      label: null,
    },
    { at: { kind: 'step', step: 70 }, change: { type: 'alarm_reset', asset_id: 'pv1' }, label: null },
  ],
  expected_points: [],
};

const info = (asset_type: 'bess' | 'pv', cause: FaultCauseInfo['cause']): FaultCauseInfo => ({
  asset_type,
  cause,
  label: cause,
  severity: 'fault',
  alrm: [],
  evt1: [],
  fault_code: 0,
  p_max_factor: 1,
  p_available_factor: 1,
});
const CATALOG = [info('bess', 'trip'), info('bess', 'over_temperature'), info('pv', 'trip'), info('pv', 'ground_fault')];

describe('scenarioEdits', () => {
  it('round-trips a scenario through the row model', () => {
    const rows = SCENARIO.events.map(rowFromEvent);
    expect(scenarioFromRows('Trip, sag, restore', rows)).toEqual(SCENARIO);
  });

  it('offers the targets each change type can take', () => {
    expect(targetsFor({ ...blankRow(), type: 'breaker' }, REFERENCE_SITE)).toEqual(['poi', 'bess1', 'bess2', 'pv1', 'load1']);
    expect(targetsFor({ ...blankRow(), type: 'asset_fault' }, REFERENCE_SITE)).toEqual(['bess1', 'bess2', 'pv1']);
    expect(targetsFor({ ...blankRow(), type: 'comm_loss', commTarget: 'meter' }, REFERENCE_SITE)).toEqual([
      'm_bess1', 'm_bess2', 'm_pv1',
    ]);
    expect(targetsFor({ ...blankRow(), type: 'comm_loss', commTarget: 'poi_meter' }, REFERENCE_SITE)).toEqual([]);
    expect(targetsFor({ ...blankRow(), type: 'alarm_reset' }, REFERENCE_SITE)).toEqual(['bess1', 'bess2', 'pv1']);
  });

  it("offers the catalog's causes for the asset's type", () => {
    expect(causesFor('pv1', REFERENCE_SITE, CATALOG).map((item) => item.cause)).toEqual(['trip', 'ground_fault']);
    expect(causesFor('bess2', REFERENCE_SITE, CATALOG).map((item) => item.cause)).toEqual(['trip', 'over_temperature']);
  });

  it('flags rows powerflow would reject', () => {
    const rows = [
      { ...blankRow(0) },
      { ...blankRow(), type: 'asset_fault' as const, target: 'bess1', cause: 'ground_fault' as const },
      { ...blankRow(), type: 'grid_voltage' as const, value: '2' },
      { ...blankRow(), trigger: 'sim_time' as const, simTime: 'soon' },
    ];
    expect(rowProblems(rows, REFERENCE_SITE, CATALOG)).toHaveLength(4);
    expect(rowProblems(rows, REFERENCE_SITE)).toHaveLength(3); // no catalog yet: causes unchecked
    expect(rowProblems([], REFERENCE_SITE)).toEqual(['Add at least one event.']);
    expect(rowProblems([blankRow()], REFERENCE_SITE)).toEqual([]);
    // a clear ignores the cause
    const clear = { ...blankRow(), type: 'asset_fault' as const, target: 'bess1', active: false, cause: 'ground_fault' as const };
    expect(rowProblems([clear], REFERENCE_SITE, CATALOG)).toEqual([]);
  });

  it('round-trips expected points and keeps them on save', () => {
    const expected = [
      { device: 'bess.bess1', point: 'InvSt', equals: 'FAULT', tolerance: 0, bits_set: [], bits_clear: [], from_step: 5, to_step: 89, note: null },
      { device: 'poi_meter.meter', point: 'Hz', equals: 59.3, tolerance: 0.03, bits_set: [], bits_clear: [], from_step: 5, to_step: null, note: 'wander' },
      { device: 'bess.bess1', point: 'Evt1', equals: null, tolerance: 0, bits_set: ['A', 'B'], bits_clear: ['C'], from_step: 1, to_step: 2, note: null },
    ];
    const rows = expected.map(expectedRowFrom);
    expect(rows.map(expectedPointFrom)).toEqual(expected);
    const scenario = scenarioFromRows('d', SCENARIO.events.map(rowFromEvent), rows);
    expect(scenario.expected_points).toEqual(expected);
  });

  it('flags expected-point rows powerflow would reject', () => {
    expect(expectedRowProblems([{ ...blankExpectedRow(), device: 'bess.bess1', point: 'W', equals: '0' }])).toEqual([]);
    expect(expectedRowProblems([blankExpectedRow()])).toHaveLength(2); // no device/point, nothing to check
    expect(
      expectedRowProblems([{ ...blankExpectedRow(), device: 'd', point: 'p', bitsSet: 'X', fromStep: '5', toStep: '2' }]),
    ).toEqual(['Expected point 1: the to step must be ≥ the from step.']);
  });

  it('describes expected points in one line', () => {
    expect(describeExpectation({ device: 'd', point: 'Hz', equals: 59.3, tolerance: 0.03, from_step: 1 })).toBe('Hz = 59.3 ± 0.03');
    expect(describeExpectation({ device: 'd', point: 'Alrm', bits_set: ['OVER_TEMP'], bits_clear: ['X'], tolerance: 0, from_step: 1 })).toBe(
      'Alrm has OVER_TEMP; clear X',
    );
  });

  it('describes changes in one line', () => {
    expect(SCENARIO.events.map((event) => describeChange(event.change))).toEqual([
      'fault pv1 (ground_fault)',
      'grid voltage 0.9 pu',
      'restore comms to POI meter',
      'open breaker poi',
      'restore grid frequency',
      'fault bess1 (trip, auto-restore)',
      'reset alarms on pv1',
    ]);
  });
});
