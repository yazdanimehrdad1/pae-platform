import type {
  CommTarget,
  ConditionChange,
  EventScenario,
  ExpectedPoint,
  FaultAssetType,
  FaultCause,
  FaultCauseInfo,
  ScenarioEvent,
  SiteConfig,
} from '@/api/types/powerflow';

// The event scenario editor's flat row model (one row per event, every field present so a form
// can bind to it) and its conversion to and from powerflow's EventScenario. Pure.

export type ChangeType = ConditionChange['type'];

export interface EventRow {
  trigger: 'step' | 'sim_time';
  step: number; // the Nth step after the scenario starts
  simTime: string; // ISO 8601 (UTC)
  type: ChangeType;
  target: string; // breaker id / asset id / meter id
  commTarget: CommTarget;
  closed: boolean; // breaker
  active: boolean; // fault, comm loss
  cause: FaultCause;
  autoRestore: boolean; // fault: clears itself 2-10 min of sim time later (no latch)
  value: string; // grid voltage (pu) or frequency (Hz); '' = restore
  label: string;
}

export const CHANGE_LABELS: Record<ChangeType, string> = {
  breaker: 'Breaker',
  asset_fault: 'Asset fault',
  alarm_reset: 'Alarm reset',
  comm_loss: 'Comm loss',
  grid_voltage: 'Grid voltage',
  grid_frequency: 'Grid frequency',
};

export function blankRow(step = 1): EventRow {
  return {
    trigger: 'step',
    step,
    simTime: '',
    type: 'breaker',
    target: 'poi',
    commTarget: 'asset',
    closed: false,
    active: true,
    cause: 'trip',
    autoRestore: false,
    value: '',
    label: '',
  };
}

export function rowFromEvent(event: ScenarioEvent): EventRow {
  const row = blankRow();
  if (event.at.kind === 'step') row.step = event.at.step;
  else {
    row.trigger = 'sim_time';
    row.simTime = event.at.sim_time;
  }
  row.label = event.label ?? '';
  const change = event.change;
  row.type = change.type ?? 'breaker';
  switch (change.type) {
    case 'breaker':
      row.target = change.breaker;
      row.closed = change.closed;
      break;
    case 'asset_fault':
      row.target = change.asset_id;
      row.active = change.active ?? true;
      row.cause = change.cause ?? 'trip';
      row.autoRestore = change.auto_restore ?? false;
      break;
    case 'alarm_reset':
      row.target = change.asset_id;
      break;
    case 'comm_loss':
      row.commTarget = change.target;
      row.target = change.id ?? '';
      row.active = change.active ?? true;
      break;
    case 'grid_voltage':
      row.value = change.vm_pu == null ? '' : String(change.vm_pu);
      break;
    case 'grid_frequency':
      row.value = change.hz == null ? '' : String(change.hz);
      break;
  }
  return row;
}

export function changeFromRow(row: EventRow): ConditionChange {
  const value = row.value.trim() === '' ? null : Number(row.value);
  switch (row.type) {
    case 'breaker':
      return { type: 'breaker', breaker: row.target, closed: row.closed };
    case 'asset_fault':
      return {
        type: 'asset_fault',
        asset_id: row.target,
        active: row.active,
        cause: row.cause,
        auto_restore: row.autoRestore,
      };
    case 'alarm_reset':
      return { type: 'alarm_reset', asset_id: row.target };
    case 'comm_loss':
      return {
        type: 'comm_loss',
        target: row.commTarget,
        id: row.commTarget === 'poi_meter' ? null : row.target,
        active: row.active,
      };
    case 'grid_voltage':
      return { type: 'grid_voltage', vm_pu: value };
    case 'grid_frequency':
      return { type: 'grid_frequency', hz: value };
  }
}

/** The expected-points editor's row: every field a string so inputs can bind to it. */
export interface ExpectedRow {
  device: string;
  point: string;
  equals: string; // a number, an enum symbol, or '' (none)
  tolerance: string;
  bitsSet: string; // comma-separated bit labels
  bitsClear: string;
  fromStep: string;
  toStep: string; // '' = only fromStep
  note: string;
}

export function blankExpectedRow(): ExpectedRow {
  return { device: '', point: '', equals: '', tolerance: '', bitsSet: '', bitsClear: '', fromStep: '1', toStep: '', note: '' };
}

export function expectedRowFrom(expected: ExpectedPoint): ExpectedRow {
  return {
    device: expected.device,
    point: expected.point,
    equals: expected.equals == null ? '' : String(expected.equals),
    tolerance: expected.tolerance ? String(expected.tolerance) : '',
    bitsSet: (expected.bits_set ?? []).join(', '),
    bitsClear: (expected.bits_clear ?? []).join(', '),
    fromStep: String(expected.from_step),
    toStep: expected.to_step == null ? '' : String(expected.to_step),
    note: expected.note ?? '',
  };
}

const symbols = (text: string) =>
  text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

export function expectedPointFrom(row: ExpectedRow): ExpectedPoint {
  const equals = row.equals.trim();
  return {
    device: row.device.trim(),
    point: row.point.trim(),
    // A number is a number; anything else is an enum symbol (e.g. FAULT).
    equals: equals === '' ? null : Number.isNaN(Number(equals)) ? equals : Number(equals),
    tolerance: row.tolerance.trim() === '' ? 0 : Number(row.tolerance),
    bits_set: symbols(row.bitsSet),
    bits_clear: symbols(row.bitsClear),
    from_step: Number(row.fromStep),
    to_step: row.toStep.trim() === '' ? null : Number(row.toStep),
    note: row.note.trim() || null,
  };
}

/** The point-standard device labels a site has, for suggestions ("bess.bess1", "site.site"). */
export function deviceLabels(config: SiteConfig): string[] {
  return [
    'site.site',
    'poi_meter.meter',
    ...(config.meters ?? []).map((item) => `feeder_meter.${item.id}`),
    ...(config.bess ?? []).map((item) => `bess.${item.id}`),
    ...(config.pv ?? []).map((item) => `pv.${item.id}`),
    ...(config.loads ?? []).map((item) => `load.${item.id}`),
  ];
}

export function expectedRowProblems(rows: ExpectedRow[]): string[] {
  const problems: string[] = [];
  rows.forEach((row, index) => {
    const at = `Expected point ${index + 1}`;
    if (!row.device.trim() || !row.point.trim()) problems.push(`${at}: enter a device and a point.`);
    if (!row.equals.trim() && !symbols(row.bitsSet).length && !symbols(row.bitsClear).length) {
      problems.push(`${at}: give a value, bits set or bits clear.`);
    }
    const from = Number(row.fromStep);
    if (!(Number.isInteger(from) && from >= 1)) problems.push(`${at}: the from step must be 1 or more.`);
    if (row.toStep.trim() !== '' && !(Number(row.toStep) >= from)) problems.push(`${at}: the to step must be ≥ the from step.`);
    if (row.tolerance.trim() !== '' && !(Number(row.tolerance) >= 0)) problems.push(`${at}: the tolerance must be ≥ 0.`);
  });
  return problems;
}

/** One line for an expected point, e.g. "InvSt = FAULT", "Alrm has OVER_TEMP", "Hz = 59.3 ± 0.03". */
export function describeExpectation(expected: ExpectedPoint): string {
  const parts: string[] = [];
  if (expected.equals != null) {
    parts.push(`= ${expected.equals}${expected.tolerance ? ` ± ${expected.tolerance}` : ''}`);
  }
  if (expected.bits_set?.length) parts.push(`has ${expected.bits_set.join(', ')}`);
  if (expected.bits_clear?.length) parts.push(`clear ${expected.bits_clear.join(', ')}`);
  return `${expected.point} ${parts.join('; ')}`;
}

export function stepWindow(expected: ExpectedPoint): string {
  return expected.to_step == null || expected.to_step === expected.from_step
    ? `step ${expected.from_step}`
    : `steps ${expected.from_step}–${expected.to_step}`;
}

export function scenarioFromRows(
  description: string,
  rows: EventRow[],
  expectedRows: ExpectedRow[] = [],
): EventScenario {
  return {
    schema_version: 1,
    description: description.trim() || null,
    expected_points: expectedRows.map(expectedPointFrom),
    events: rows.map((row) => ({
      at:
        row.trigger === 'step'
          ? { kind: 'step', step: row.step }
          : { kind: 'sim_time', sim_time: new Date(row.simTime).toISOString() },
      change: changeFromRow(row),
      label: row.label.trim() || null,
    })),
  };
}

/** The ids a row's target can be, for its change type, on this site. */
export function targetsFor(row: EventRow, config: SiteConfig): string[] {
  const bess = (config.bess ?? []).map((item) => item.id);
  const pv = (config.pv ?? []).map((item) => item.id);
  const loads = (config.loads ?? []).map((item) => item.id);
  switch (row.type) {
    case 'breaker':
      return ['poi', ...bess, ...pv, ...loads];
    case 'asset_fault':
    case 'alarm_reset':
      return [...bess, ...pv];
    case 'comm_loss':
      if (row.commTarget === 'poi_meter') return [];
      return row.commTarget === 'meter' ? (config.meters ?? []).map((item) => item.id) : [...bess, ...pv, ...loads];
    default:
      return [];
  }
}

export function faultAssetType(assetId: string, config: SiteConfig): FaultAssetType {
  return (config.pv ?? []).some((pv) => pv.id === assetId) ? 'pv' : 'bess';
}

/** The catalog's causes for this asset's type (faults first, in catalog order). */
export function causesFor(assetId: string, config: SiteConfig, catalog: FaultCauseInfo[]): FaultCauseInfo[] {
  const assetType = faultAssetType(assetId, config);
  return catalog.filter((info) => info.asset_type === assetType);
}

/** Client-side checks before saving (powerflow validates again). An empty catalog (not loaded
 * yet) skips the cause check. */
export function rowProblems(rows: EventRow[], config: SiteConfig, catalog: FaultCauseInfo[] = []): string[] {
  const problems: string[] = [];
  if (rows.length === 0) problems.push('Add at least one event.');
  rows.forEach((row, index) => {
    const at = `Event ${index + 1}`;
    if (row.trigger === 'step' && !(Number.isInteger(row.step) && row.step >= 1)) problems.push(`${at}: the step must be 1 or more.`);
    if (row.trigger === 'sim_time' && Number.isNaN(Date.parse(row.simTime))) problems.push(`${at}: enter a sim time.`);
    const targets = targetsFor(row, config);
    if (targets.length > 0 && !targets.includes(row.target)) problems.push(`${at}: choose a target.`);
    const causes = causesFor(row.target, config, catalog);
    if (row.type === 'asset_fault' && row.active && catalog.length > 0 && !causes.some((info) => info.cause === row.cause)) {
      problems.push(`${at}: that cause doesn't apply.`);
    }
    if (row.type === 'grid_voltage' && row.value.trim() !== '') {
      const value = Number(row.value);
      if (!(value >= 0.5 && value <= 1.5)) problems.push(`${at}: voltage must be 0.5–1.5 pu (empty = restore).`);
    }
    if (row.type === 'grid_frequency' && row.value.trim() !== '') {
      const value = Number(row.value);
      if (!(value >= 55 && value <= 65)) problems.push(`${at}: frequency must be 55–65 Hz (empty = restore).`);
    }
  });
  return problems;
}

/** One line describing an event's change, e.g. "open breaker bess1". */
export function describeChange(change: ConditionChange): string {
  switch (change.type) {
    case 'breaker':
      return `${change.closed ? 'close' : 'open'} breaker ${change.breaker}`;
    case 'asset_fault': {
      if (change.active === false) return `clear faults on ${change.asset_id}`;
      const restore = change.auto_restore ? ', auto-restore' : '';
      return `fault ${change.asset_id} (${change.cause ?? 'trip'}${restore})`;
    }
    case 'alarm_reset':
      return `reset alarms on ${change.asset_id}`;
    case 'comm_loss': {
      const target = change.target === 'poi_meter' ? 'POI meter' : change.id;
      return change.active === false ? `restore comms to ${target}` : `lose comms to ${target}`;
    }
    case 'grid_voltage':
      return change.vm_pu == null ? 'restore grid voltage' : `grid voltage ${change.vm_pu} pu`;
    case 'grid_frequency':
      return change.hz == null ? 'restore grid frequency' : `grid frequency ${change.hz} Hz`;
    default:
      return 'change';
  }
}
