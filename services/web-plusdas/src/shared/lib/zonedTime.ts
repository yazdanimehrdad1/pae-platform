// A datetime-local input holds a wall-clock time with no zone. A report's custom period is typed in
// the site's time zone, so these convert between that wall time and a UTC instant.

const offsetFormatters = new Map<string, Intl.DateTimeFormat>();

/** How far the zone's wall clock is ahead of UTC at this instant, in ms (PDT: -7 h). */
function zoneOffsetMs(utcMs: number, timeZone: string): number {
  let formatter = offsetFormatters.get(timeZone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-US", {
      timeZone, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    offsetFormatters.set(timeZone, formatter);
  }
  const parts = Object.fromEntries(formatter.formatToParts(new Date(utcMs)).map(part => [part.type, part.value]));
  const wallAsUtc = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), Number(parts.hour), Number(parts.minute), Number(parts.second));
  return wallAsUtc - Math.floor(utcMs / 1000) * 1000;
}

/** "2026-10-13T00:00" in the zone -> "2026-10-13T07:00:00.000Z". A wall time skipped by a DST
 * change resolves to the instant just after it; a repeated one to its first occurrence. */
export function fromZonedInput(value: string, timeZone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) throw new Error(`Not a datetime-local value: ${value}`);
  const [, year, month, day, hour, minute] = match.map(Number);
  const wallAsUtc = Date.UTC(year, month - 1, day, hour, minute);
  let utcMs = wallAsUtc - zoneOffsetMs(wallAsUtc, timeZone);
  utcMs = wallAsUtc - zoneOffsetMs(utcMs, timeZone);
  return new Date(utcMs).toISOString();
}

/** "2026-10-13T07:00:00Z" -> "2026-10-13T00:00" on the zone's wall clock. */
export function toZonedInput(iso: string, timeZone: string): string {
  const utcMs = Date.parse(iso);
  return new Date(utcMs + zoneOffsetMs(utcMs, timeZone)).toISOString().slice(0, 16);
}
