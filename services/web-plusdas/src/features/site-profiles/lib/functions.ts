import type { ProfileDevice, SiteFunction } from '@/api/types/siteProfiles';

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
