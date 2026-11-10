import type { ProfileDevice, SiteFunction } from '@/api/types/siteProfiles';
import { formatSiteTime } from '@/shared/lib/siteTime';

/** The windows a site function can be tried over (the gateway allows at most 31 days). */
export const WINDOWS = [
  { label: 'Last hour', hours: 1 },
  { label: 'Last 24 hours', hours: 24 },
  { label: 'Last 7 days', hours: 24 * 7 },
  { label: 'Last 30 days', hours: 24 * 30 },
] as const;

/** The approved devices a function runs for: none for a site-wide one, else those of its types. */
export function devicesFor(fn: SiteFunction, devices: ProfileDevice[]): ProfileDevice[] {
  if (fn.kind !== 'device') return [];
  const types = fn.device_types ?? [];
  return devices.filter(device => types.length === 0 || types.includes(device.type));
}

/** Where a function runs: the whole site, or each device of its types. */
export function appliesTo(fn: SiteFunction): string {
  if (fn.kind !== 'device') return 'Whole site';
  const types = fn.device_types ?? [];
  return types.length ? `Each ${types.join(' / ')}` : 'Each device';
}

// An ISO 8601 timestamp with a UTC offset, as the gateway returns them ("2026-11-09T22:21:06Z").
const ISO_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

/** A function result with every timestamp shown in `timeZone` ("09 Nov, 14:21 PST") instead of
 * UTC. For display only: the AI gets the result as the gateway returns it (UTC). */
export function withDisplayTimes(value: unknown, timeZone: string): unknown {
  if (typeof value === 'string') return ISO_TIMESTAMP.test(value) ? formatSiteTime(value, timeZone, { withDate: true }) : value;
  if (Array.isArray(value)) return value.map(entry => withDisplayTimes(entry, timeZone));
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, withDisplayTimes(entry, timeZone)]));
  }
  return value;
}
