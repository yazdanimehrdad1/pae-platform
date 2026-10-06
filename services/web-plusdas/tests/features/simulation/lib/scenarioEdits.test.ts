import { describe, expect, it } from 'vitest';
import type { EventScenario } from '@/api/types/powerflow';
import {
  blankRow,
  describeChange,
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
    { at: { kind: 'step', step: 10 }, change: { type: 'asset_fault', asset_id: 'pv1', active: true, cause: 'ground_fault' }, label: 'trip' },
    { at: { kind: 'sim_time', sim_time: '2026-06-21T12:00:00.000Z' }, change: { type: 'grid_voltage', vm_pu: 0.9 }, label: null },
    { at: { kind: 'step', step: 30 }, change: { type: 'comm_loss', target: 'poi_meter', id: null, active: false }, label: null },
    { at: { kind: 'step', step: 40 }, change: { type: 'breaker', breaker: 'poi', closed: false }, label: null },
    { at: { kind: 'step', step: 50 }, change: { type: 'grid_frequency', hz: null }, label: null },
  ],
};

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
  });

  it('flags rows powerflow would reject', () => {
    const rows = [
      { ...blankRow(0) },
      { ...blankRow(), type: 'asset_fault' as const, target: 'bess1', cause: 'ground_fault' as const },
      { ...blankRow(), type: 'grid_voltage' as const, value: '2' },
      { ...blankRow(), trigger: 'sim_time' as const, simTime: 'soon' },
    ];
    expect(rowProblems(rows, REFERENCE_SITE)).toHaveLength(4);
    expect(rowProblems([], REFERENCE_SITE)).toEqual(['Add at least one event.']);
    expect(rowProblems([blankRow()], REFERENCE_SITE)).toEqual([]);
  });

  it('describes changes in one line', () => {
    expect(SCENARIO.events.map((event) => describeChange(event.change))).toEqual([
      'fault pv1 (ground_fault)',
      'grid voltage 0.9 pu',
      'restore comms to POI meter',
      'open breaker poi',
      'restore grid frequency',
    ]);
  });
});
