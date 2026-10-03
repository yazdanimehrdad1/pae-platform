import { DEFAULT_DISCRETE_MODE, isDiscreteModeId, type DiscreteModeId } from "../components/discrete/discreteModes";

// The user's chosen way to draw status points, kept per user next to their trends.
const STORAGE_KEY_PREFIX = "historian_discrete_mode_";

export function loadDiscreteMode(userId: string): DiscreteModeId {
  try {
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${userId}`);
    return isDiscreteModeId(stored) ? stored : DEFAULT_DISCRETE_MODE;
  } catch {
    return DEFAULT_DISCRETE_MODE;
  }
}

export function saveDiscreteMode(userId: string, mode: DiscreteModeId): void {
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${userId}`, mode);
  } catch {
    // Storage unavailable (private window, quota): the choice just isn't remembered.
  }
}
