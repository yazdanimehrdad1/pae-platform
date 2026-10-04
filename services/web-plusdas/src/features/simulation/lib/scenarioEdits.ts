import type {
  CommTarget,
  ConditionChange,
  EventScenario,
  FaultCause,
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
  value: string; // grid voltage (pu) or frequency (Hz); '' = restore
  label: string;
}

export const CHANGE_LABELS: Record<ChangeType, string> = {
  breaker: 'Breaker',
  asset_fault: 'Asset fault',
  comm_loss: 'Comm loss',
  grid_voltage: 'Grid voltage',
  grid_frequency: 'Grid frequency',
};

export const BESS_CAUSES: FaultCause[] = ['trip', 'over_temperature'];
export const PV_CAUSES: FaultCause[] = ['trip', 'ground_fault', 'dc_overvoltage'];

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
      return { type: 'asset_fault', asset_id: row.target, active: row.active, cause: row.cause };
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

export function scenarioFromRows(description: string, rows: EventRow[]): EventScenario {
  return {
    schema_version: 1,
    description: description.trim() || null,
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
      return [...bess, ...pv];
    case 'comm_loss':
      if (row.commTarget === 'poi_meter') return [];
      return row.commTarget === 'meter' ? (config.meters ?? []).map((item) => item.id) : [...bess, ...pv, ...loads];
    default:
      return [];
  }
}

export function causesFor(assetId: string, config: SiteConfig): FaultCause[] {
  return (config.pv ?? []).some((pv) => pv.id === assetId) ? PV_CAUSES : BESS_CAUSES;
}

/** Client-side checks before saving (powerflow validates again). */
export function rowProblems(rows: EventRow[], config: SiteConfig): string[] {
  const problems: string[] = [];
  if (rows.length === 0) problems.push('Add at least one event.');
  rows.forEach((row, index) => {
    const at = `Event ${index + 1}`;
    if (row.trigger === 'step' && !(Number.isInteger(row.step) && row.step >= 1)) problems.push(`${at}: the step must be 1 or more.`);
    if (row.trigger === 'sim_time' && Number.isNaN(Date.parse(row.simTime))) problems.push(`${at}: enter a sim time.`);
    const targets = targetsFor(row, config);
    if (targets.length > 0 && !targets.includes(row.target)) problems.push(`${at}: choose a target.`);
    if (row.type === 'asset_fault' && !causesFor(row.target, config).includes(row.cause)) problems.push(`${at}: that cause doesn't apply.`);
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
    case 'asset_fault':
      return change.active === false ? `clear fault on ${change.asset_id}` : `fault ${change.asset_id} (${change.cause ?? 'trip'})`;
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
