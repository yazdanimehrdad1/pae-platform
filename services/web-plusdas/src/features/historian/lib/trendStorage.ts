export interface Trend {
  id: string;
  name: string;
  points: string[];
}

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
    return trends;
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
