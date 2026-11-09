import type { ChangeKind, ChangeTarget, ProfileChange, ProfilePoint } from '@/api/types/siteProfiles';

// Records, so a kind or target added to intelli-gateway's contract fails the typecheck until it has a label.
export const CHANGE_KIND_LABELS: Record<ChangeKind, string> = { added: 'New', removed: 'Removed', changed: 'Changed' };
export const CHANGE_TARGET_LABELS: Record<ChangeTarget, string> = {
  site: 'Site', device: 'Devices', point: 'Points', function: 'Site functions', topology: 'Topology',
};
const TARGET_ORDER = Object.keys(CHANGE_TARGET_LABELS) as ChangeTarget[];

/** The id of the change that onboards a site: its first approval must include it. */
export const SITE_CHANGE_ID = 'site';

export function groupByTarget(changes: ProfileChange[]): { target: ChangeTarget; changes: ProfileChange[] }[] {
  return TARGET_ORDER
    .map(target => ({ target, changes: changes.filter(change => change.target === target) }))
    .filter(group => group.changes.length > 0);
}

/** Why the chosen changes can't be approved yet, or null when they can. */
export function approvalProblem(selected: ReadonlySet<string>, onboarded: boolean): string | null {
  if (selected.size === 0) return 'Select the changes to approve.';
  if (!onboarded && !selected.has(SITE_CHANGE_ID)) return "A new site's first approval must include the site itself.";
  return null;
}

/** The HTTP status of a failed API call (the client throws FastAPI's body plus `status`). */
export function statusOf(error: unknown): number | undefined {
  return typeof error === 'object' && error !== null ? (error as { status?: number }).status : undefined;
}

/** A point's enum or bit labels as one short line: "0 off · 1 on", bits as "bit 3 OVER_TEMP". */
export function labelsText(point: ProfilePoint): string {
  const enumLabels = Object.entries(point.enum_labels ?? {}).map(([value, label]) => `${value} ${label}`);
  const bitLabels = Object.entries(point.bit_labels ?? {}).map(([bit, label]) => `bit ${bit} ${label}`);
  return [...enumLabels, ...bitLabels].join(' · ');
}

/** The point's name without its device prefix (`INV1.active_power` -> `active_power`). */
export function localPointName(point: ProfilePoint): string {
  const prefix = `${point.device_name}.`;
  return point.name.startsWith(prefix) ? point.name.slice(prefix.length) : point.name;
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—';
}

/** React Query key of the site list; every site profile query key starts with it. */
export const SITE_PROFILES_QUERY_KEY = ["site-profiles"] as const;
