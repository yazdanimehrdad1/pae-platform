// Timestamps are shown in the site's local time with its time zone, never the browser's.

const formatters = new Map<string, Intl.DateTimeFormat>();

function formatter(timeZone: string, withDate: boolean): Intl.DateTimeFormat {
  const key = `${timeZone}|${withDate}`;
  let cached = formatters.get(key);
  if (!cached) {
    cached = new Intl.DateTimeFormat("en-GB", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
      second: withDate ? undefined : "2-digit",
      ...(withDate ? { day: "2-digit", month: "short" } : {}),
      timeZoneName: "short",
      hour12: false,
    });
    formatters.set(key, cached);
  }
  return cached;
}

/** "14:02:31 GMT-7", or with a date "26 Sept, 14:02 GMT-7". */
export function formatSiteTime(at: string | number, timeZone: string, options: { withDate?: boolean } = {}): string {
  return formatter(timeZone, options.withDate ?? false).format(new Date(at));
}

/** "45 s", "8 min", "2 h 14 min", "3 d 4 h". */
export function formatDuration(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  const days = Math.floor(hours / 24);
  return hours % 24 ? `${days} d ${hours % 24} h` : `${days} d`;
}
