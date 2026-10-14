import { BROWSER_TIME_ZONE } from "@/shared/hooks/useDisplayTimeZone";

// The IANA time zones a site can be in, for the site form's picker. The list is the browser's own
// (backend-ot accepts any IANA name and stores it canonical). supportedValuesOf is newer than the
// TypeScript lib in use, and missing in old browsers, hence the accessor and the fallback.

export interface TimeZoneOption {
  zone: string;
  /** "Los Angeles" */
  city: string;
  /** "UTC−07:00", the offset right now (it changes with DST). */
  offset: string;
}

export interface TimeZoneGroup {
  region: string;
  zones: TimeZoneOption[];
}

function supportedTimeZones(): string[] {
  const supportedValuesOf = (Intl as unknown as { supportedValuesOf?: (key: "timeZone") => string[] }).supportedValuesOf;
  return supportedValuesOf?.("timeZone") ?? [];
}

export function isTimeZone(value: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}

/** The zone's offset from UTC at `at`: "UTC+05:30", "UTC−07:00", "UTC+00:00". */
export function utcOffset(zone: string, at: Date = new Date()): string {
  const name = new Intl.DateTimeFormat("en-US", { timeZone: zone, timeZoneName: "longOffset" })
    .formatToParts(at)
    .find(part => part.type === "timeZoneName")?.value ?? "GMT";
  const offset = name.replace("GMT", "");
  return `UTC${offset === "" ? "+00:00" : offset.replace("-", "−")}`;
}

function toOption(zone: string, at: Date): TimeZoneOption {
  const city = zone.includes("/") ? zone.slice(zone.indexOf("/") + 1).replace(/_/g, " ").replace(/\//g, " / ") : zone;
  return { zone, city, offset: utcOffset(zone, at) };
}

/** Every zone, grouped by region (UTC first, then regions A to Z, cities A to Z). `extra` (e.g. a
 * site's stored zone the browser doesn't list) is included too. */
export function timeZoneGroups(extra: string[] = [], at: Date = new Date()): TimeZoneGroup[] {
  const zones = [...new Set(["UTC", BROWSER_TIME_ZONE, ...supportedTimeZones(), ...extra])].filter(isTimeZone);
  const byRegion = new Map<string, TimeZoneOption[]>();
  for (const zone of zones) {
    const region = zone.includes("/") ? zone.slice(0, zone.indexOf("/")) : "UTC";
    byRegion.set(region, [...(byRegion.get(region) ?? []), toOption(zone, at)]);
  }
  return [...byRegion]
    .map(([region, options]) => ({ region, zones: options.sort((first, second) => first.zone.localeCompare(second.zone)) }))
    .sort((first, second) => (first.region === "UTC" ? -1 : second.region === "UTC" ? 1 : first.region.localeCompare(second.region)));
}
