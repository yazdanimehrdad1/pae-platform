import type { Trend } from "../types";
import { isAxisScale } from "./axes";
import { sanitizeSeriesStyles } from "./seriesStyles";

const STORAGE_KEY_PREFIX = "historian_trends_";

function getStorageKey(userId: string): string {
  return `${STORAGE_KEY_PREFIX}${userId}`;
}

export function loadTrendsFromStorage(userId: string): Trend[] {
  try {
    const stored = localStorage.getItem(getStorageKey(userId));
    if (!stored) return [{ id: '1', name: 'Default Trend', points: [] }];
    const trends = JSON.parse(stored) as Trend[];
    if (!Array.isArray(trends) || trends.length === 0) return [{ id: '1', name: 'Default Trend', points: [] }];
    // A scale this version doesn't know is dropped, so the trend falls back to per unit; so are
    // invalid styles, so those lines fall back to their default look.
    return trends.map(({ styles, ...trend }) => {
      const loaded: Trend = trend.scale === undefined || isAxisScale(trend.scale) ? trend : { ...trend, scale: undefined };
      const validStyles = sanitizeSeriesStyles(styles);
      return validStyles ? { ...loaded, styles: validStyles } : loaded;
    });
  } catch {
    return [{ id: '1', name: 'Default Trend', points: [] }];
  }
}

export function saveTrendsToStorage(userId: string, trends: Trend[]): void {
  try {
    localStorage.setItem(getStorageKey(userId), JSON.stringify(trends));
  } catch (error) {
    console.error('Error saving trends:', error);
    if (error instanceof DOMException && error.name === 'QuotaExceededError') {
      console.warn('localStorage quota exceeded.');
    }
  }
}

export function clearTrendsFromStorage(userId: string): void {
  try {
    localStorage.removeItem(getStorageKey(userId));
  } catch (error) {
    console.error('Error clearing trends:', error);
  }
}
